"""Gestión de configuración, database.csv y personas.csv."""

import json
import os
import uuid
import logging
from typing import List, Tuple
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

APP_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = APP_DIR / "config.json"
PERSONAS_PATH = APP_DIR / "personas.csv"
CARAS_DIR = APP_DIR / "caras"

DEFAULT_CONFIG = {
    "base_folder": "",
    "last_analysis": None,
    "yolo_confidence": 0.4,
    "face_tolerance": 0.6,
    "min_face_px": 40,
    "min_blur_var": 15.0,
}

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff"}


# ── Config ──────────────────────────────────────────────────────────────

def load_config() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        for k, v in DEFAULT_CONFIG.items():
            cfg.setdefault(k, v)
        return cfg
    save_config(DEFAULT_CONFIG)
    return dict(DEFAULT_CONFIG)


def save_config(cfg: dict):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


# ── Personas ────────────────────────────────────────────────────────────

def load_personas() -> pd.DataFrame:
    if PERSONAS_PATH.exists():
        return pd.read_csv(PERSONAS_PATH, dtype=str).fillna("")
    return pd.DataFrame(columns=["fingerprint", "nombre"])


def save_personas(df: pd.DataFrame):
    df.to_csv(PERSONAS_PATH, index=False, encoding="utf-8")


def set_persona_name(fingerprint: str, nombre: str):
    df = load_personas()
    if fingerprint in df["fingerprint"].values:
        df.loc[df["fingerprint"] == fingerprint, "nombre"] = nombre
    else:
        df = pd.concat(
            [df, pd.DataFrame([{"fingerprint": fingerprint, "nombre": nombre}])],
            ignore_index=True,
        )
    save_personas(df)


def get_persona_name(fingerprint: str) -> str:
    df = load_personas()
    row = df.loc[df["fingerprint"] == fingerprint]
    if not row.empty:
        return row.iloc[0]["nombre"]
    return ""


# ── Database CSV ────────────────────────────────────────────────────────

def database_path(base_folder: str) -> Path:
    return Path(base_folder) / "database.csv"


def load_database(base_folder: str) -> pd.DataFrame:
    p = database_path(base_folder)
    if p.exists():
        return pd.read_csv(p, dtype=str).fillna("")
    return pd.DataFrame(columns=["filename", "rel_path", "tags", "persons"])


def save_database(base_folder: str, df: pd.DataFrame):
    df.to_csv(database_path(base_folder), index=False, encoding="utf-8")


def scan_images(base_folder: str) -> List[Path]:
    base = Path(base_folder)
    images = []
    for f in base.rglob("*"):
        if f.suffix.lower() in IMAGE_EXTENSIONS and f.name != "database.csv":
            images.append(f)
    return sorted(images)


def sync_database(base_folder: str, force: bool = False) -> Tuple[pd.DataFrame, List[Path]]:
    """Devuelve (df_existente, lista_de_nuevas_imagenes_a_procesar)."""
    db = load_database(base_folder)
    on_disk = scan_images(base_folder)
    base = Path(base_folder)

    disk_rels = {str(f.relative_to(base)) for f in on_disk}

    if force:
        db = pd.DataFrame(columns=["filename", "rel_path", "tags", "persons"])
        new_images = on_disk
    else:
        # Eliminar filas de archivos que ya no existen
        if not db.empty:
            mask = db["rel_path"].isin(disk_rels)
            removed = len(db) - mask.sum()
            if removed > 0:
                logger.info("Eliminadas %d filas de archivos no encontrados en disco", removed)
            db = db[mask].reset_index(drop=True)

        existing_rels = set(db["rel_path"].values) if not db.empty else set()
        new_images = [f for f in on_disk if str(f.relative_to(base)) not in existing_rels]

    return db, new_images


def new_fingerprint() -> str:
    return str(uuid.uuid4())


def merge_fingerprints(keep: str, remove: str, base_folder: str):
    """Fusiona dos fingerprints: mueve recortes y actualiza database.csv."""
    # Mover recortes
    src = CARAS_DIR / remove
    dst = CARAS_DIR / keep
    dst.mkdir(parents=True, exist_ok=True)
    if src.exists():
        for f in src.iterdir():
            f.rename(dst / f.name)
        src.rmdir()

    # Actualizar database.csv
    if base_folder:
        db = load_database(base_folder)
        if not db.empty:
            def replace_fp(val):
                parts = val.split("|") if val else []
                parts = [keep if p == remove else p for p in parts]
                # Deduplicar
                seen = set()
                result = []
                for p in parts:
                    if p not in seen:
                        seen.add(p)
                        result.append(p)
                return "|".join(result)

            db["persons"] = db["persons"].apply(replace_fp)
            save_database(base_folder, db)

    # Actualizar personas.csv: si remove tenía nombre y keep no, transferir
    personas = load_personas()
    remove_row = personas.loc[personas["fingerprint"] == remove]
    keep_row = personas.loc[personas["fingerprint"] == keep]
    if not remove_row.empty:
        remove_name = remove_row.iloc[0]["nombre"]
        if remove_name and (keep_row.empty or not keep_row.iloc[0]["nombre"]):
            set_persona_name(keep, remove_name)
        personas = personas[personas["fingerprint"] != remove].reset_index(drop=True)
        save_personas(personas)

    logger.info("Fusionados fingerprints: %s → %s", remove, keep)
