"""
Yuz tanish utility (face identification).
Foydalaniladi: edu_admin bot — admin rasm yuboradi, tizim tinglovchini taniydi.

Usullar (prioritet bo'yicha):
  1. face_recognition (dlib) — o'rnatilgan bo'lsa eng aniq
  2. mediapipe FaceMesh landmark cosine similarity — o'rta aniqlik
  3. Fallback — bo'sh ro'yxat (handler manual ro'yxat ko'rsatadi)

O'rnatish (1-usul uchun, ixtiyoriy):
  pip install face_recognition
  # Windows uchun avval dlib kerak:
  # pip install cmake && pip install dlib
"""
import logging
import os

import numpy as np

logger = logging.getLogger(__name__)

# Minimal o'xshashlik chegaralari
FACE_REC_THRESHOLD  = 0.55   # distance <= bu → topildi  (kichikroq = aniqroq)
MEDIAPIPE_THRESHOLD = 0.985  # cosine similarity >= bu → topildi (kattaroq = aniqroq)


# ─────────────────────────────────────────────────────────────
# 1-usul: face_recognition (dlib)
# ─────────────────────────────────────────────────────────────

def _face_rec_distances(query_path: str, candidate_paths: list[str]) -> list[float] | None:
    """Qaytaradi: distance ro'yxati (0=mukammal, 1=umuman o'xshamas) yoki None"""
    try:
        import face_recognition  # noqa

        q_img  = face_recognition.load_image_file(query_path)
        q_encs = face_recognition.face_encodings(q_img)
        if not q_encs:
            logger.info("face_recognition: so'rov rasmida yuz topilmadi")
            return None

        q_enc = q_encs[0]
        dists = []
        for cpath in candidate_paths:
            try:
                if not os.path.exists(cpath):
                    dists.append(1.0)
                    continue
                c_img  = face_recognition.load_image_file(cpath)
                c_encs = face_recognition.face_encodings(c_img)
                if c_encs:
                    d = float(face_recognition.face_distance([c_encs[0]], q_enc)[0])
                    dists.append(d)
                else:
                    dists.append(1.0)
            except Exception as ex:
                logger.debug(f"face_recognition candidate xatosi: {ex}")
                dists.append(1.0)
        return dists

    except ImportError:
        logger.info("face_recognition o'rnatilmagan — keyingi usulga o'tiladi")
        return None
    except Exception as ex:
        logger.warning(f"face_recognition xatosi: {ex}")
        return None


# ─────────────────────────────────────────────────────────────
# 2-usul: mediapipe FaceMesh cosine similarity
# ─────────────────────────────────────────────────────────────

def _get_landmark_vector(image_path: str) -> np.ndarray | None:
    """468 ta FaceMesh landmark → normalize qilingan vektor"""
    try:
        import mediapipe as mp
        from PIL import Image

        img = Image.open(image_path).convert("RGB")
        arr = np.array(img)

        mp_mesh = mp.solutions.face_mesh
        with mp_mesh.FaceMesh(
            static_image_mode=True,
            max_num_faces=1,
            refine_landmarks=False,
            min_detection_confidence=0.5,
        ) as mesh:
            res = mesh.process(arr)
            if not res.multi_face_landmarks:
                return None

            lms = res.multi_face_landmarks[0].landmark
            xs = [lm.x for lm in lms]
            ys = [lm.y for lm in lms]
            cx = sum(xs) / len(xs)
            cy = sum(ys) / len(ys)
            scale = max(max(xs) - min(xs), max(ys) - min(ys)) or 1.0

            vec = []
            for lm in lms:
                vec.extend([(lm.x - cx) / scale, (lm.y - cy) / scale])
            return np.array(vec, dtype=np.float32)

    except ImportError:
        logger.info("mediapipe o'rnatilmagan")
        return None
    except Exception as ex:
        logger.debug(f"landmark vektor xatosi: {ex}")
        return None


def _cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def _mediapipe_similarities(query_path: str, candidate_paths: list[str]) -> list[float] | None:
    """Qaytaradi: cosine similarity ro'yxati yoki None"""
    q_vec = _get_landmark_vector(query_path)
    if q_vec is None:
        return None

    sims = []
    for cpath in candidate_paths:
        try:
            if not os.path.exists(cpath):
                sims.append(0.0)
                continue
            c_vec = _get_landmark_vector(cpath)
            sims.append(_cosine_sim(q_vec, c_vec) if c_vec is not None else 0.0)
        except Exception:
            sims.append(0.0)
    return sims if any(s > 0 for s in sims) else None


# ─────────────────────────────────────────────────────────────
# Asosiy funksiya
# ─────────────────────────────────────────────────────────────

def recognize_student(
    query_path: str,
    students: list[dict],
    top_n: int = 3,
) -> dict:
    """
    Admin yuborgan rasm bo'yicha tinglovchini taniydi.

    Parametrlar:
        query_path  — admin yuborgan rasmning absolyut yo'li
        students    — [{'id', 'full_name', 'image_path', ...}, ...]
        top_n       — qaytariladigan nomzodlar soni

    Qaytaradi:
        {
          'method':     'face_recognition' | 'mediapipe' | None,
          'found':      True | False,
          'best_match': {'id', 'full_name', 'score', ...} | None,
          'candidates': [{'id', 'full_name', 'score'}, ...],  # top_n ta
        }
    """
    if not students:
        return {'method': None, 'found': False, 'best_match': None, 'candidates': []}

    valid = [s for s in students if s.get('image_path') and os.path.exists(s['image_path'])]
    if not valid:
        return {'method': None, 'found': False, 'best_match': None, 'candidates': []}

    paths = [s['image_path'] for s in valid]

    # ── 1. face_recognition ──────────────────────────────────
    method  = None
    scores  = None   # higher = better

    dists = _face_rec_distances(query_path, paths)
    if dists is not None:
        method = 'face_recognition'
        scores = [max(0.0, 1.0 - d) * 100 for d in dists]   # → 0‒100 %

    # ── 2. mediapipe ─────────────────────────────────────────
    if scores is None:
        sims = _mediapipe_similarities(query_path, paths)
        if sims is not None:
            method = 'mediapipe'
            scores = [s * 100 for s in sims]

    if scores is None:
        return {'method': None, 'found': False, 'best_match': None, 'candidates': []}

    # Nomzodlarni tartiblash
    ranked = sorted(
        [
            {
                'id':        valid[i]['id'],
                'full_name': valid[i]['full_name'],
                'phone':     valid[i].get('phone', ''),
                'score':     round(scores[i], 1),
                'method':    method,
            }
            for i in range(len(valid))
        ],
        key=lambda x: x['score'],
        reverse=True,
    )
    candidates = ranked[:top_n]

    # Topildi hisoblanish sharti
    best = candidates[0] if candidates else None
    threshold = (
        (1 - FACE_REC_THRESHOLD) * 100   # ~45%
        if method == 'face_recognition'
        else MEDIAPIPE_THRESHOLD * 100   # ~98.5%
    )
    found = bool(best and best['score'] >= threshold)

    return {
        'method':     method,
        'found':      found,
        'best_match': best if found else None,
        'candidates': candidates,
    }
