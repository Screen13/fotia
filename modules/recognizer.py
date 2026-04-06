"""Gestión de encodings faciales en memoria y operaciones de reconocimiento."""

import logging
import pickle
from typing import Dict, List, Optional
from pathlib import Path

import numpy as np

from modules.database import CARAS_DIR

logger = logging.getLogger(__name__)


class FaceStore:
    """Almacena encodings faciales en memoria para comparación rápida."""

    def __init__(self):
        self.encodings: Dict[str, List[np.ndarray]] = {}
        self._encoding_cache_path = CARAS_DIR / ".encodings_cache.pkl"

    def load_from_disk(self):
        """Carga encodings desde el cache en disco."""
        self.encodings.clear()
        if self._encoding_cache_path.exists():
            try:
                with open(self._encoding_cache_path, "rb") as f:
                    data = pickle.load(f)
                for fp, enc_list in data.items():
                    self.encodings[fp] = [np.array(e) for e in enc_list]
                logger.info(
                    "Cargados %d fingerprints con %d encodings totales desde cache",
                    len(self.encodings),
                    sum(len(v) for v in self.encodings.values()),
                )
            except Exception as e:
                logger.warning("Error cargando cache de encodings: %s", e)
                self.encodings.clear()

    def save_to_disk(self):
        """Persiste los encodings a disco."""
        CARAS_DIR.mkdir(parents=True, exist_ok=True)
        data = {fp: [e.tolist() for e in enc_list] for fp, enc_list in self.encodings.items()}
        with open(self._encoding_cache_path, "wb") as f:
            pickle.dump(data, f)
        logger.info("Cache de encodings guardado (%d fingerprints)", len(self.encodings))

    def add_encoding(self, fingerprint: str, encoding: np.ndarray):
        """Añade un encoding a un fingerprint."""
        if fingerprint not in self.encodings:
            self.encodings[fingerprint] = []
        self.encodings[fingerprint].append(encoding)

    def get_all_fingerprints(self) -> List[str]:
        """Devuelve todos los fingerprints conocidos."""
        # Incluir también carpetas en /caras/ que puedan no tener encodings cacheados
        fps = set(self.encodings.keys())
        if CARAS_DIR.exists():
            for d in CARAS_DIR.iterdir():
                if d.is_dir() and d.name != ".encodings_cache.pkl":
                    fps.add(d.name)
        return sorted(fps)

    def get_face_images(self, fingerprint: str, limit: int = 50) -> List[Path]:
        """Devuelve las rutas de recortes de cara para un fingerprint."""
        face_dir = CARAS_DIR / fingerprint
        if not face_dir.exists():
            return []
        images = sorted(face_dir.glob("*.jpg"), key=lambda f: f.stat().st_mtime, reverse=True)
        return images[:limit]

    def merge(self, keep: str, remove: str):
        """Fusiona encodings de remove en keep."""
        if remove in self.encodings:
            if keep not in self.encodings:
                self.encodings[keep] = []
            self.encodings[keep].extend(self.encodings.pop(remove))
        self.save_to_disk()
