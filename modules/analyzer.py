"""Análisis de imágenes: detección de objetos (YOLO) y detección/reconocimiento facial."""

import logging
import time
from typing import Dict, List, Optional, Tuple
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# Traducción de las 80 clases COCO (YOLOv8) al español
COCO_ES = {
    "person": "persona", "bicycle": "bicicleta", "car": "coche", "motorcycle": "moto",
    "airplane": "avión", "bus": "autobús", "train": "tren", "truck": "camión",
    "boat": "barco", "traffic light": "semáforo", "fire hydrant": "hidrante",
    "stop sign": "señal de stop", "parking meter": "parquímetro", "bench": "banco",
    "bird": "pájaro", "cat": "gato", "dog": "perro", "horse": "caballo",
    "sheep": "oveja", "cow": "vaca", "elephant": "elefante", "bear": "oso",
    "zebra": "cebra", "giraffe": "jirafa", "backpack": "mochila", "umbrella": "paraguas",
    "handbag": "bolso", "tie": "corbata", "suitcase": "maleta", "frisbee": "frisbee",
    "skis": "esquís", "snowboard": "snowboard", "sports ball": "pelota",
    "kite": "cometa", "baseball bat": "bate", "baseball glove": "guante de béisbol",
    "skateboard": "monopatín", "surfboard": "tabla de surf", "tennis racket": "raqueta",
    "bottle": "botella", "wine glass": "copa", "cup": "taza", "fork": "tenedor",
    "knife": "cuchillo", "spoon": "cuchara", "bowl": "cuenco", "banana": "plátano",
    "apple": "manzana", "sandwich": "sándwich", "orange": "naranja", "broccoli": "brócoli",
    "carrot": "zanahoria", "hot dog": "perrito caliente", "pizza": "pizza",
    "donut": "donut", "cake": "tarta", "chair": "silla", "couch": "sofá",
    "potted plant": "planta", "bed": "cama", "dining table": "mesa",
    "toilet": "inodoro", "tv": "televisor", "laptop": "portátil", "mouse": "ratón",
    "remote": "mando", "keyboard": "teclado", "cell phone": "móvil",
    "microwave": "microondas", "oven": "horno", "toaster": "tostadora",
    "sink": "fregadero", "refrigerator": "nevera", "book": "libro", "clock": "reloj",
    "vase": "jarrón", "scissors": "tijeras", "teddy bear": "peluche",
    "hair drier": "secador", "toothbrush": "cepillo de dientes",
}

# Lazy-loaded globals
_yolo_model = None
_face_rec = None


def _get_yolo():
    global _yolo_model
    if _yolo_model is None:
        from ultralytics import YOLO
        _yolo_model = YOLO("yolov8n.pt")
        logger.info("Modelo YOLOv8n cargado")
    return _yolo_model


def _get_face_recognition():
    global _face_rec
    if _face_rec is None:
        import face_recognition as fr
        _face_rec = fr
        logger.info("Librería face_recognition cargada")
    return _face_rec


def detect_objects(image_path: str, confidence: float = 0.4) -> List[str]:
    """Devuelve lista de etiquetas únicas detectadas en la imagen."""
    model = _get_yolo()
    results = model(image_path, verbose=False, conf=confidence)
    tags = set()
    for r in results:
        if r.boxes is not None:
            for box in r.boxes:
                cls_id = int(box.cls[0])
                label = model.names[cls_id]
                tags.add(COCO_ES.get(label, label))
    return sorted(tags)


def _is_face_too_small(location: tuple, min_px: int = 40) -> bool:
    top, right, bottom, left = location
    return (bottom - top) < min_px or (right - left) < min_px


def _is_face_blurry(img_rgb: np.ndarray, location: tuple, min_var: float = 15.0) -> bool:
    top, right, bottom, left = location
    face_crop = img_rgb[top:bottom, left:right]
    gray = cv2.cvtColor(face_crop, cv2.COLOR_RGB2GRAY)
    variance = cv2.Laplacian(gray, cv2.CV_64F).var()
    return variance < min_var


def detect_faces(
    image_path: str, min_face_px: int = 40, min_blur_var: float = 15.0,
) -> List[Tuple[np.ndarray, tuple]]:
    """Devuelve lista de (encoding_128d, (top, right, bottom, left)) para cada cara.
    Filtra caras demasiado pequeñas o borrosas."""
    fr = _get_face_recognition()
    img = fr.load_image_file(image_path)
    locations = fr.face_locations(img, model="hog")
    if not locations:
        return []

    # Filtrar antes de calcular encodings (que es costoso)
    valid_locations = []
    for loc in locations:
        if _is_face_too_small(loc, min_face_px):
            logger.debug("Cara descartada (muy pequeña %dpx): %s", loc[2] - loc[0], loc)
            continue
        if _is_face_blurry(img, loc, min_blur_var):
            logger.debug("Cara descartada (borrosa): %s", loc)
            continue
        valid_locations.append(loc)

    if not valid_locations:
        return []

    encodings = fr.face_encodings(img, known_face_locations=valid_locations)
    return list(zip(encodings, valid_locations))


def match_face(
    encoding: np.ndarray,
    known_encodings: Dict[str, List[np.ndarray]],
    tolerance: float = 0.6,
) -> Optional[str]:
    """Compara un encoding contra los conocidos. Devuelve fingerprint o None.

    Usa dos criterios para reducir falsos positivos:
    - La distancia media de los encodings que coinciden debe estar bajo la tolerancia
    - Al menos el 30% de los encodings conocidos deben coincidir (si hay 2+)
    """
    import face_recognition as fr

    best_fp = None
    best_score = tolerance

    for fp, enc_list in known_encodings.items():
        if not enc_list:
            continue
        distances = fr.face_distance(enc_list, encoding)
        matches = distances < tolerance
        n_matches = int(np.sum(matches))

        if n_matches == 0:
            continue

        # Con 2+ encodings conocidos, exigir que al menos 30% coincidan
        if len(enc_list) >= 2:
            match_ratio = n_matches / len(enc_list)
            if match_ratio < 0.3:
                continue

        # Usar la media de las distancias que coinciden como score
        avg_dist = float(np.mean(distances[matches]))

        if avg_dist < best_score:
            best_score = avg_dist
            best_fp = fp

    return best_fp


def crop_face(image_path: str, location: tuple, output_path: str):
    """Recorta una cara de la imagen y la guarda."""
    img = cv2.imread(image_path)
    if img is None:
        return
    top, right, bottom, left = location
    # Añadir margen
    h, w = img.shape[:2]
    margin_y = int((bottom - top) * 0.2)
    margin_x = int((right - left) * 0.2)
    top = max(0, top - margin_y)
    bottom = min(h, bottom + margin_y)
    left = max(0, left - margin_x)
    right = min(w, right + margin_x)

    face_img = img[top:bottom, left:right]
    cv2.imwrite(output_path, face_img)
