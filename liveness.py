"""
Passive liveness / anti-spoofing (presentation-attack detection).

Wraps a MiniFASNet CNN (AntiSpoofing_bin_1.5_128.onnx from the hairymax
Face-AntiSpoofing project) run through OpenCV's DNN module - no extra runtime
dependency. Given a camera frame and a face box, it returns the probability
that the face belongs to a real, live person (as opposed to a printed photo or
a screen).

Model classes:  0 = REAL (live),  1 = FAKE (spoof).  Real probability = softmax[0].
Input: RGB face crop expanded by 1.5x, resized/padded to 128x128, scaled to /255.
"""
import os

import cv2
import numpy as np

import config


def increased_crop(img_rgb, face_xywh, bbox_inc=1.5):
    """Square crop around the face, expanded by bbox_inc, black-padded if needed.

    Mirrors the crop the anti-spoof model was trained/served with.
    """
    real_h, real_w = img_rgb.shape[:2]
    x, y, w, h = face_xywh
    l = max(w, h)
    xc, yc = x + w / 2, y + h / 2
    x = int(xc - l * bbox_inc / 2)
    y = int(yc - l * bbox_inc / 2)
    x1, y1 = max(0, x), max(0, y)
    x2 = real_w if x + l * bbox_inc > real_w else int(x + l * bbox_inc)
    y2 = real_h if y + l * bbox_inc > real_h else int(y + l * bbox_inc)

    crop = img_rgb[y1:y2, x1:x2, :]
    # When the face is close to the camera the expanded box runs past the frame
    # edges. Replicate the edge pixels instead of adding black bars - the model
    # was never trained on black-bordered faces and would call them "spoof".
    crop = cv2.copyMakeBorder(
        crop,
        y1 - y, int(l * bbox_inc - y2 + y),
        x1 - x, int(l * bbox_inc) - x2 + x,
        cv2.BORDER_REPLICATE,
    )
    return crop


class LivenessDetector:
    def __init__(self, model_path=None, size=128):
        self.size = size
        path = model_path or config.ANTISPOOF_PATH
        self.net = cv2.dnn.readNetFromONNX(path) if os.path.exists(path) else None
        self.model_path = path

    def available(self):
        return self.net is not None

    def _preprocess(self, crop_rgb):
        new = self.size
        oh, ow = crop_rgb.shape[:2]
        ratio = float(new) / max(oh, ow)
        nh, nw = int(oh * ratio), int(ow * ratio)
        img = cv2.resize(crop_rgb, (nw, nh))
        dh, dw = new - nh, new - nw
        top, bottom = dh // 2, dh - dh // 2
        left, right = dw // 2, dw - dw // 2
        img = cv2.copyMakeBorder(img, top, bottom, left, right,
                                 cv2.BORDER_CONSTANT, value=[0, 0, 0])
        blob = img.transpose(2, 0, 1).astype(np.float32) / 255.0
        return np.expand_dims(blob, axis=0)

    def real_score(self, frame_bgr, face_xywh):
        """Return P(real) in [0, 1], or None if the model is unavailable."""
        if self.net is None:
            return None
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        crop = increased_crop(rgb, face_xywh, config.ANTISPOOF_BBOX_INC)
        self.net.setInput(self._preprocess(crop))
        logits = self.net.forward().flatten()
        e = np.exp(logits - logits.max())
        p = e / e.sum()
        return float(p[0])  # class 0 = real

    def is_real(self, frame_bgr, face_xywh):
        """Return (is_real, score). Fails OPEN (treats as real) if model missing."""
        p = self.real_score(frame_bgr, face_xywh)
        if p is None:
            return True, None
        return p >= config.ANTISPOOF_THRESHOLD, p


def yaw_proxy(face_row):
    """A rough head-yaw indicator from YuNet's 5 landmarks.

    Uses the nose position relative to the eye midpoint, normalised by the
    inter-eye distance. It shifts when the head turns left/right, so the RANGE
    of this value over several frames reveals whether the head actually moved
    (something a static photo can't do).
    """
    reye = face_row[4:6]
    leye = face_row[6:8]
    nose = face_row[8:10]
    eye_mid_x = (reye[0] + leye[0]) / 2.0
    inter = float(np.hypot(leye[0] - reye[0], leye[1] - reye[1])) + 1e-6
    return float((nose[0] - eye_mid_x) / inter)


class ActiveLiveness:
    """Per-student liveness state: a smoothed passive score + a movement check.

    The passive score is noisy frame to frame (especially as the person moves
    closer/further), so we keep a short window and use its MEDIAN rather than
    trusting any single frame. A spoof decision is only made after a few frames
    have been seen (warm-up), so approaching the camera doesn't flash "SPOOF".
    """

    def __init__(self):
        self.state = {}

    def update(self, key, real_prob, yaw):
        st = self.state.setdefault(key, {"probs": [], "yaw": []})
        if real_prob is not None:
            st["probs"].append(real_prob)
            st["probs"] = st["probs"][-config.SMOOTH_WINDOW:]
        st["yaw"].append(yaw)
        st["yaw"] = st["yaw"][-30:]
        return st

    def smoothed_real(self, key):
        """Median real-probability over the recent window, or None if no model."""
        p = self.state.get(key, {}).get("probs", [])
        return float(np.median(p)) if p else None

    def _warm(self, key):
        return len(self.state.get(key, {}).get("probs", [])) >= config.SMOOTH_MIN

    def is_spoof(self, key):
        """True only once enough frames agree the face is not live."""
        s = self.smoothed_real(key)
        if s is None:
            return False  # no passive model -> can't call it spoof
        return self._warm(key) and s < config.ANTISPOOF_THRESHOLD

    def real_enough(self, key):
        s = self.smoothed_real(key)
        if s is None:  # no passive model: just need a few frames seen
            return len(self.state.get(key, {}).get("yaw", [])) >= config.ACTIVE_REAL_FRAMES
        return self._warm(key) and s >= config.ANTISPOOF_THRESHOLD

    def moved(self, key):
        y = self.state.get(key, {}).get("yaw", [])
        return (max(y) - min(y)) >= config.ACTIVE_MOVE_RATIO if len(y) >= 2 else False

    def passed(self, key):
        """Marked only when the face is reliably real AND the head has moved."""
        if not config.ACTIVE_LIVENESS_ENABLED:
            return self.real_enough(key)
        return self.real_enough(key) and self.moved(key)
