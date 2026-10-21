"""
Shared face engine: detection (YuNet) + embedding (SFace).

One embedding per face is enough to recognise a person, so this supports
single-photo enrollment. Embeddings are L2-normalised, which makes cosine
similarity a simple dot product.
"""
import cv2
import numpy as np

import config


class FaceEngine:
    def __init__(self):
        config.check_models()
        # Input size is updated per-frame in detect(); (320, 320) is a placeholder.
        self.detector = cv2.FaceDetectorYN.create(
            config.YUNET_PATH, "", (320, 320),
            config.DET_SCORE_THRESH, config.DET_NMS_THRESH, config.DET_TOPK,
        )
        self.recognizer = cv2.FaceRecognizerSF.create(config.SFACE_PATH, "")

    def detect(self, image):
        """Return an (N, 15) array of faces: [x, y, w, h, 5 landmarks, score].

        Large images are downscaled before detection for reliability, then the
        geometry (first 14 columns) is scaled back to the original image so the
        rows can be used with alignCrop on the full-resolution frame.
        """
        h, w = image.shape[:2]
        scale = min(1.0, config.DET_MAX_SIDE / max(h, w))
        if scale < 1.0:
            det_img = cv2.resize(image, (int(w * scale), int(h * scale)))
        else:
            det_img = image

        dh, dw = det_img.shape[:2]
        self.detector.setInputSize((dw, dh))
        _, faces = self.detector.detect(det_img)
        if faces is None:
            return np.empty((0, 15), dtype=np.float32)

        faces = faces.astype(np.float32)
        if scale < 1.0:
            faces[:, :14] /= scale   # map coords/landmarks back to original size
        return faces

    def embed(self, image, face_row):
        """Align + crop one detected face and return its L2-normalised embedding."""
        aligned = self.recognizer.alignCrop(image, face_row)
        feat = self.recognizer.feature(aligned).flatten().astype(np.float32)
        norm = np.linalg.norm(feat)
        return feat / norm if norm > 0 else feat

    def largest_face(self, faces):
        """Return the row of the biggest detected face, or None."""
        if len(faces) == 0:
            return None
        return faces[np.argmax(faces[:, 2] * faces[:, 3])]

    def embed_largest(self, image):
        """Convenience: detect faces and embed the largest one. Returns embedding or None."""
        face = self.largest_face(self.detect(image))
        return self.embed(image, face) if face is not None else None

    def embed_references(self, image):
        """Return a list of reference embeddings for an enrollment photo.

        The original image plus, if config.USE_FLIP_AUGMENT is on, a
        horizontally-flipped copy (a free extra viewpoint). Empty list if no
        face is found.
        """
        embs = []
        e = self.embed_largest(image)
        if e is not None:
            embs.append(e)
        if config.USE_FLIP_AUGMENT:
            f = self.embed_largest(cv2.flip(image, 1))
            if f is not None:
                embs.append(f)
        return embs
