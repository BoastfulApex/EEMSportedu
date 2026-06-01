"""
Yuz aniqlash utility.
mediapipe mavjud bo'lsa — haqiqiy tekshiruv.
mavjud bo'lmasa — True (fallback).
"""
import logging

logger = logging.getLogger(__name__)


def detect_face(image_path: str) -> bool:
    """
    Rasmda yuz borligini tekshiradi.
    True  → yuz aniqlandi (rasm qabul qilinadi)
    False → yuz aniqlanmadi (rasm rad etiladi)
    """
    try:
        import mediapipe as mp
        from PIL import Image
        import numpy as np

        img = Image.open(image_path).convert("RGB")
        img_array = np.array(img)

        mp_face = mp.solutions.face_detection
        with mp_face.FaceDetection(
            model_selection=1,
            min_detection_confidence=0.5
        ) as face_detection:
            results = face_detection.process(img_array)
            if results.detections:
                logger.info(f"Yuz aniqlandi: {image_path} ({len(results.detections)} ta)")
                return True
            else:
                logger.info(f"Yuz aniqlanmadi: {image_path}")
                return False

    except ImportError:
        logger.warning("mediapipe o'rnatilmagan — fallback: True")
        return True
    except Exception as e:
        logger.error(f"detect_face xatosi: {e}")
        return True
