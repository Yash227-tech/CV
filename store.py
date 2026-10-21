"""
Enrollment storage: an .npz file holding face embeddings.

A student may have SEVERAL reference embeddings (e.g. with and without
spectacles, or different angles). Each reference is one row; rows for the same
student share the same id. At attendance time a face is matched to the BEST
(highest-similarity) reference across all students, which makes recognition
robust to appearance changes like removing glasses.

Backward compatible with older single-embedding files (which simply had one
row per id).
"""
import os

import numpy as np

import config


def load_enrollments():
    """Return (ids, names, embeddings).

    embeddings is (N, 128) float32; ids/names are length-N lists. There may be
    multiple rows (references) with the same id. Empty if nobody is enrolled.
    """
    if not os.path.exists(config.ENROLL_PATH):
        return [], [], np.empty((0, 128), dtype=np.float32)
    data = np.load(config.ENROLL_PATH, allow_pickle=True)
    return list(data["ids"]), list(data["names"]), data["embeddings"].astype(np.float32)


def save_enrollments(ids, names, embeddings):
    config.ensure_dirs()
    np.savez(
        config.ENROLL_PATH,
        ids=np.array(ids, dtype=object),
        names=np.array(names, dtype=object),
        embeddings=np.array(embeddings, dtype=np.float32).reshape(-1, 128),
    )


def student_count():
    """Number of unique students enrolled (not number of reference photos)."""
    ids, _, _ = load_enrollments()
    return len(set(ids))


def reference_count(student_id):
    """How many reference embeddings a student currently has."""
    ids, _, _ = load_enrollments()
    return ids.count(str(student_id).strip())


def roster():
    """Return [(id, name, num_references)] with one entry per unique student."""
    ids, names, _ = load_enrollments()
    seen = {}
    for sid, name in zip(ids, names):
        if sid not in seen:
            seen[sid] = [name, 0]
        seen[sid][1] += 1
    return [(sid, info[0], info[1]) for sid, info in seen.items()]


def add_references(student_id, name, embeddings):
    """Append one or more reference embeddings for a student (keeps existing)."""
    student_id = str(student_id).strip()
    ids, names, embs = load_enrollments()
    embs = list(embs)
    for e in embeddings:
        ids.append(student_id)
        names.append(name)
        embs.append(e)
    save_enrollments(ids, names, embs)
    return reference_count(student_id), student_count()


def set_references(student_id, name, embeddings):
    """Replace ALL of a student's references with the given embeddings."""
    student_id = str(student_id).strip()
    ids, names, embs = load_enrollments()
    kept = [(i, n, e) for i, n, e in zip(ids, names, embs) if i != student_id]
    ids = [k[0] for k in kept]
    names = [k[1] for k in kept]
    embs = [k[2] for k in kept]
    for e in embeddings:
        ids.append(student_id)
        names.append(name)
        embs.append(e)
    save_enrollments(ids, names, embs)
    return reference_count(student_id), student_count()


# Backwards-compatible single-embedding helper (replace a student's references).
def upsert(student_id, name, embedding):
    existed = reference_count(student_id) > 0
    set_references(student_id, name, [embedding])
    return ("updated" if existed else "added"), student_count()


def delete(student_id):
    """Remove a student and ALL their reference embeddings.

    Returns (removed_name_or_None, remaining_unique_students).
    """
    student_id = str(student_id).strip()
    ids, names, embs = load_enrollments()
    if student_id not in ids:
        return None, len(set(ids))
    removed_name = names[ids.index(student_id)]
    kept = [(i, n, e) for i, n, e in zip(ids, names, embs) if i != student_id]
    save_enrollments([k[0] for k in kept], [k[1] for k in kept], [k[2] for k in kept])
    return removed_name, student_count()
