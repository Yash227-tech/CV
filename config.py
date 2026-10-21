"""
Central configuration for the Face Recognition Attendance prototype.

This version uses deep face EMBEDDINGS (OpenCV YuNet detector + SFace
recognizer), which work from a SINGLE photo per student. All paths resolve
relative to this file so the project runs from anywhere.
"""
import os

# ---- Project paths ----------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

MODEL_DIR = os.path.join(BASE_DIR, "model")              # model files + enrollments
ATTENDANCE_DIR = os.path.join(BASE_DIR, "attendance")    # daily attendance CSVs

# Pre-trained ONNX models (downloaded from the OpenCV Zoo).
YUNET_PATH = os.path.join(MODEL_DIR, "face_detection_yunet_2023mar.onnx")
SFACE_PATH = os.path.join(MODEL_DIR, "face_recognition_sface_2021dec.onnx")

# Where enrolled students' face embeddings are stored.
ENROLL_PATH = os.path.join(MODEL_DIR, "enrollments.npz")

# Remembered subject names (so they appear in the GUI dropdown across sessions).
SUBJECTS_PATH = os.path.join(MODEL_DIR, "subjects.json")

# ---- Camera -----------------------------------------------------------------
CAMERA_INDEX = 0            # 0 = default webcam; change if you have multiple cams

# ---- Detector (YuNet) settings ----------------------------------------------
DET_SCORE_THRESH = 0.7      # minimum face-detection confidence
DET_NMS_THRESH = 0.3
DET_TOPK = 5000
# Large images are downscaled so their longer side is at most this many pixels
# before detection (YuNet can miss faces in very high-res photos). Face
# coordinates are mapped back to the original image afterwards.
DET_MAX_SIDE = 640

# ---- Recognition (SFace) ----------------------------------------------------
# Faces are matched by COSINE similarity of their 128-d embeddings.
# Score is in [-1, 1]; HIGHER = more similar. 0.363 is OpenCV's recommended
# cosine threshold for SFace. Raise it to be stricter, lower to be more lenient.
COSINE_THRESHOLD = 0.363

# During enrollment, also store the embedding of a horizontally-flipped copy of
# the photo. This is a free extra reference that improves robustness to pose.
# (It does NOT help with glasses on/off - for that, add a second photo of the
# student in the other state via the "add another photo" option.)
USE_FLIP_AUGMENT = True


def ensure_dirs():
    """Create the folders the project needs if they don't exist yet."""
    for d in (MODEL_DIR, ATTENDANCE_DIR):
        os.makedirs(d, exist_ok=True)


def check_models():
    """Fail early with a clear message if the ONNX models are missing."""
    missing = [p for p in (YUNET_PATH, SFACE_PATH) if not os.path.exists(p)]
    if missing:
        raise SystemExit(
            "Missing model file(s):\n  " + "\n  ".join(missing) +
            "\n\nDownload them into the 'model/' folder (see README.md)."
        )
