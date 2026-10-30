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


def _p(path):
    """The .npz to use. Defaults to the students' enrollment file; pass
    config.TEACHER_ENROLL_PATH to operate on the teacher face store instead."""
    return path or config.ENROLL_PATH


def load_enrollments(path=None):
    """Return (ids, names, embeddings).

    embeddings is (N, 128) float32; ids/names are length-N lists. There may be
    multiple rows (references) with the same id. Empty if nobody is enrolled.
    """
    p = _p(path)
    if not os.path.exists(p):
        return [], [], np.empty((0, 128), dtype=np.float32)
    data = np.load(p, allow_pickle=True)
    return list(data["ids"]), list(data["names"]), data["embeddings"].astype(np.float32)


def save_enrollments(ids, names, embeddings, path=None):
    config.ensure_dirs()
    np.savez(
        _p(path),
        ids=np.array(ids, dtype=object),
        names=np.array(names, dtype=object),
        embeddings=np.array(embeddings, dtype=np.float32).reshape(-1, 128),
    )


def student_count(path=None):
    """Number of unique people enrolled (not number of reference photos)."""
    ids, _, _ = load_enrollments(path)
    return len(set(ids))


def reference_count(student_id, path=None):
    """How many reference embeddings a person currently has."""
    ids, _, _ = load_enrollments(path)
    return ids.count(str(student_id).strip())


def roster(path=None):
    """Return [(id, name, num_references)] with one entry per unique person."""
    ids, names, _ = load_enrollments(path)
    seen = {}
    for sid, name in zip(ids, names):
        if sid not in seen:
            seen[sid] = [name, 0]
        seen[sid][1] += 1
    return [(sid, info[0], info[1]) for sid, info in seen.items()]


def add_references(student_id, name, embeddings, path=None):
    """Append one or more reference embeddings for a person (keeps existing)."""
    student_id = str(student_id).strip()
    ids, names, embs = load_enrollments(path)
    embs = list(embs)
    for e in embeddings:
        ids.append(student_id)
        names.append(name)
        embs.append(e)
    save_enrollments(ids, names, embs, path)
    return reference_count(student_id, path), student_count(path)


def set_references(student_id, name, embeddings, path=None):
    """Replace ALL of a person's references with the given embeddings."""
    student_id = str(student_id).strip()
    ids, names, embs = load_enrollments(path)
    kept = [(i, n, e) for i, n, e in zip(ids, names, embs) if i != student_id]
    ids = [k[0] for k in kept]
    names = [k[1] for k in kept]
    embs = [k[2] for k in kept]
    for e in embeddings:
        ids.append(student_id)
        names.append(name)
        embs.append(e)
    save_enrollments(ids, names, embs, path)
    return reference_count(student_id, path), student_count(path)


# Backwards-compatible single-embedding helper (replace a person's references).
def upsert(student_id, name, embedding, path=None):
    existed = reference_count(student_id, path) > 0
    set_references(student_id, name, [embedding], path)
    return ("updated" if existed else "added"), student_count(path)


def delete(student_id, path=None):
    """Remove a person and ALL their reference embeddings.

    Returns (removed_name_or_None, remaining_unique_people).
    """
    student_id = str(student_id).strip()
    ids, names, embs = load_enrollments(path)
    if student_id not in ids:
        return None, len(set(ids))
    removed_name = names[ids.index(student_id)]
    kept = [(i, n, e) for i, n, e in zip(ids, names, embs) if i != student_id]
    save_enrollments([k[0] for k in kept], [k[1] for k in kept], [k[2] for k in kept], path)
    return removed_name, student_count(path)
