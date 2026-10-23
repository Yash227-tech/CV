# Face Recognition Attendance (Prototype)

A computer-vision attendance system built with **Python + OpenCV** that works
from a **single photo per student**. It enrolls each student from one image,
then marks attendance automatically into a daily CSV file.

Because only one sample per person is available, this uses **deep face
embeddings** instead of a classifier that needs many samples:

- **YuNet** — a fast CNN face *detector*
- **SFace** — a face *recognizer* that turns each face into a 128-number
  "fingerprint" (embedding)

Recognition is then just **comparing fingerprints**: the live face is matched to
whichever enrolled student it is most similar to (cosine similarity). No
per-student training is required, so one photo is enough.

Both models ship as small ONNX files from the OpenCV Zoo and run through
`opencv-contrib-python` — **no dlib / CMake / Visual Studio** setup.

## How it works

```
Image / Webcam ──► Detect face (YuNet) ──► Embed face (SFace) ──► 128-d vector
                                                                      │
Enroll:   store the vector as the student's reference  ◄──────────────┤
Attend:   compare live vector to all references (cosine) ─────────────┘
          best match ≥ threshold  ──►  mark present in daily CSV
```

| Script | What it does |
|--------|--------------|
| `gui.py` | **Graphical interface** (Tkinter) for everything below |
| `enroll.py` | Enroll students from a single photo each (file, folder, or webcam snapshot) |
| `attendance.py` | Recognize faces live, or mark manually; writes per-subject CSVs |
| `report.py` | Per-student attendance %, per subject; CSV export |
| `main.py` | Command-line menu that runs everything |
| `face_engine.py` | Shared detect + embed helper |
| `store.py` | Loads/saves the enrolled embeddings (`model/enrollments.npz`) |
| `config.py` | Paths and settings |

### Features

- **Single-photo enrollment** (deep embeddings — no 50-sample capture, no training)
- **Multiple subjects** — attendance is tracked separately per subject
- **Face attendance** — automatic recognition from the webcam
- **Manual attendance** — mark a student present without the camera (each row is
  tagged `face` or `manual`)
- **Graphical UI** (Tkinter) and a command-line menu

## Setup

Requires Python 3.8+ and a webcam.

```bash
pip install -r requirements.txt
```

**Model files** (already in `model/`): if you ever need them again:

- `face_detection_yunet_2023mar.onnx` — detector (OpenCV Zoo)
- `face_recognition_sface_2021dec.onnx` — recognizer (OpenCV Zoo)
- `AntiSpoofing_bin_1.5_128.onnx` — liveness / anti-spoof model
  ([hairymax/Face-AntiSpoofing](https://github.com/hairymax/Face-AntiSpoofing),
  `saved_models/`)

## Usage

### Graphical interface (easiest)

```bash
python gui.py
```

A tabbed desktop app:

- **Students** — enroll (image / webcam / folder) via inline ID/Name fields,
  add another photo, delete, all shown in a table.
- **Attendance** — pick a subject **once** from a dropdown (saved for next
  time), then "Start Face Attendance" or mark students manually; a live list
  shows who's present today for that subject, and a teacher can **Remove
  selected** to delete a wrong attendance record.
- **Reports** — per-student attendance % per subject, with CSV export.

### Command-line menu

```bash
python main.py
```

### Or run each step directly

**1. Enroll students (one photo each):**

```bash
# From a single image file
python enroll.py --image photos/alice.jpg --id 101 --name "Alice"

# From a folder of photos named "<id>_<name>.jpg"  (e.g. 101_Alice.jpg)
python enroll.py --dir photos

# From a webcam snapshot (press SPACE to capture)
python enroll.py --webcam --id 101 --name "Alice"

# List enrolled students, or delete one
python enroll.py --list
python enroll.py --delete 101
```

> Re-enrolling an existing ID updates that student's face. To remove a student
> entirely, use `--delete` (CLI), the "List / delete enrolled students" menu
> option, or the "Manage / delete students" button in the GUI.

### Improving accuracy (multiple reference photos)

A student can have **several reference photos**, and a face is matched to the
**best** one. This fixes appearance changes that a single photo can't cover —
most commonly **wearing spectacles at enrollment but not at attendance** (or
vice versa). Add a second photo of the student in the other state:

```bash
# Add an extra reference (does NOT replace the existing photo)
python enroll.py --image photos/alice_no_glasses.jpg --id 101 --append
python enroll.py --webcam --id 101 --append
```

In the GUI use **"Add another photo (e.g. no glasses)"**; in the CLI menu use
option **4**. Each enrollment also auto-stores a horizontally-flipped version
(`USE_FLIP_AUGMENT` in `config.py`) for extra pose robustness.

If a known student still reads as "Unknown", lower `COSINE_THRESHOLD` slightly
(e.g. 0.33) and/or add a reference photo taken in the attendance lighting.

**2. Take attendance for a subject (face):**

```bash
python attendance.py --subject Maths        # press q to stop
```

**3. Reports:**

```bash
python report.py                       # all subjects
python report.py --subject Maths       # one subject
python report.py --subject Maths --date 2026-10-21   # one day
python report.py --subject Maths --export            # write summary.csv
```

During webcam use a window opens — press **`q`** to quit (SPACE to capture in
`--webcam` enroll).

## Output & sessions

Attendance is saved **per session** (one lecture). Each "Start Face Attendance"
is a session, named by date + a label (the start time by default, or a label
you type such as `L1`). This is how **two lectures of the same subject in one
day** stay separate, e.g.:

```
attendance/Maths/Maths_2026-10-23_L1.csv
attendance/Maths/Maths_2026-10-23_L2.csv
```

```csv
id,name,date,time,method
101,Alice,2026-10-23,09:14:02,face
102,Bob,2026-10-23,09:14:05,manual
```

Each student is marked **once per session**. Attendance % in the report is
**sessions attended / total sessions**. The `method` column records whether the
mark came from face recognition or a manual entry.

In the GUI's Attendance page: pick an **existing session** from the dropdown to
view/edit it, or type a **New lecture label** (or leave blank) and press Start
to begin a new one.

### Teacher check-in (required before students)

A lecture must be **opened by the teacher** before any student can be marked for
it. On the Attendance page: enter the **Teacher** name and click **Open lecture
(teacher check-in)**. Until then, *Start Face Attendance* and *Mark present
(manual)* are blocked, and the session shows **"Not open — teacher check-in
required"** (it turns green **"Open (teacher: …)"** once checked in). In the CLI,
use *"Open a lecture (teacher check-in)"* first. Opening also counts the lecture
as *held* in the report, even if no student attends.

## Tuning (`config.py`)

- `CAMERA_INDEX` — change if the wrong camera opens (try `1`, `2`, ...).
- `COSINE_THRESHOLD` — similarity needed to accept a match (higher = match),
  default **0.363** (OpenCV's recommended value for SFace). Raise it to be
  stricter about "Unknown", lower it to be more lenient.
- `DET_SCORE_THRESH` — minimum face-detection confidence.
- `DET_MAX_SIDE` — big photos are downscaled to this longer-side size before
  detection (YuNet can miss faces in very high-res images).
- `ANTISPOOF_ENABLED` / `ANTISPOOF_THRESHOLD` — turn liveness on/off and set how
  strict the "real face" check is (higher = stricter).
- `ACTIVE_LIVENESS_ENABLED`, `ACTIVE_REAL_FRAMES`, `ACTIVE_MOVE_RATIO` — the
  move/turn-your-head challenge and how much movement it requires.

## Anti-spoofing (stops photos / phone screens)

A printed photo or a phone/laptop screen held to the camera would otherwise be
recognised as the real student. Two layers prevent this, both applied before a
student is marked present:

1. **Passive** — a CNN (MiniFASNet) classifies each face as **real vs spoof**,
   catching the recapture artifacts of a photo or screen (flatness, moiré,
   glare, bezels). Faces below `ANTISPOOF_THRESHOLD` are shown as `SPOOF?` and
   never marked.
2. **Active** — the student must be seen as real for a few frames **and turn
   their head slightly**; a flat photo can't, so it's rejected. On screen the
   box reads `turn head slowly` until the challenge passes.

This runs automatically during face attendance (not for manual marking). It
needs a real webcam to exercise, and a high-quality **video replay** can still
sometimes defeat the passive layer — defeating video too needs depth/IR
hardware.

**If a real student is wrongly flagged `SPOOF?`** (e.g. when close to the
camera): the score is median-smoothed over `SMOOTH_WINDOW` frames to stop
single-frame flicker, and the crop uses edge replication so a face filling the
frame isn't surrounded by black bars. If it still happens, **lower**
`ANTISPOOF_THRESHOLD` (e.g. 0.4) and keep a little space so the whole face and
some background are visible. If spoofs get through, **raise** it (e.g. 0.6).

## Why this instead of "collect 50 samples + LBPH"?

LBPH (and most classical classifiers) need **many** samples per person and
degrade badly with one. Deep embeddings are trained on millions of faces, so a
**single** reference photo already gives a strong, discriminative fingerprint —
exactly the one-shot setting here. In testing, a student enrolled from one photo
was correctly recognised in a *different* photo with a clear margin over other
people.

## Notes & limitations (useful for a report)

- Enroll with a **clear, well-lit, roughly frontal** photo for best results.
- **Liveness / anti-spoofing is built in** (passive CNN + move-your-head
  challenge) to reject printed photos and phone screens. A high-quality video
  replay can still sometimes pass the passive layer; depth/IR hardware would be
  needed to fully stop that.
- Very low-contrast or heavily stylised images (e.g. old prints) may fail
  detection.
- Accuracy still depends on lighting, pose, and camera quality at attendance
  time.

## Project layout

```
Mini/
├── config.py
├── face_engine.py       # detect (YuNet) + embed (SFace)
├── store.py             # enrolled embeddings storage
├── enroll.py            # single-photo enrollment
├── liveness.py          # anti-spoofing: passive CNN + active move/turn check
├── attendance.py        # recognize + mark attendance (per subject, + manual)
├── report.py            # per-student attendance %, export
├── subjects.py          # remembered subject names for the GUI dropdown
├── gui.py               # Tkinter graphical interface
├── main.py              # command-line menu
├── requirements.txt
├── model/               # ONNX models + enrollments.npz (created on enroll)
└── attendance/          # per-subject folders of daily CSVs
    └── <Subject>/<Subject>_<date>.csv
```
