"""Lógica de búsqueda en database.csv y personas.csv."""

import unicodedata
import logging

import pandas as pd

from modules.database import load_database, load_personas

logger = logging.getLogger(__name__)


def _normalize(text: str) -> str:
    """Normaliza texto: minúsculas y sin tildes."""
    text = text.lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return text


def search(base_folder: str, query: str) -> pd.DataFrame:
    """
    Busca en tags y nombres de personas.
    Múltiples palabras separadas por espacio: la imagen debe coincidir con TODOS los términos.
    Cada término puede coincidir en tags O en nombres de personas.
    Devuelve DataFrame con columnas: filename, rel_path, tags, persons, persons_display.
    """
    if not query.strip():
        return pd.DataFrame()

    terms = _normalize(query.strip()).split()
    if not terms:
        return pd.DataFrame()

    db = load_database(base_folder)
    personas = load_personas()

    if db.empty:
        return pd.DataFrame()

    # Crear mapa fingerprint → nombre
    fp_to_name = {}
    if not personas.empty:
        for _, row in personas.iterrows():
            if row["nombre"]:
                fp_to_name[row["fingerprint"]] = row["nombre"]

    # Para cada fila, construir un texto combinado de tags + nombres de personas
    def _row_matches_all_terms(row):
        # Texto de tags normalizado
        tags_text = _normalize(row["tags"]) if row["tags"] else ""
        # Nombres de personas en esta imagen
        person_names = ""
        if row["persons"]:
            fps = row["persons"].split("|")
            names = [_normalize(fp_to_name[fp]) for fp in fps if fp in fp_to_name]
            person_names = " ".join(names)
        combined_text = tags_text + " " + person_names
        return all(term in combined_text for term in terms)

    mask = db.apply(_row_matches_all_terms, axis=1)
    combined = db[mask].copy()
    combined = combined.drop_duplicates(subset=["rel_path"]).sort_values("rel_path").reset_index(drop=True)

    # Añadir columna de display de personas
    def persons_display(val):
        if not val:
            return ""
        parts = val.split("|")
        names = [fp_to_name.get(fp, fp[:8] + "...") for fp in parts if fp]
        return ", ".join(names)

    combined["persons_display"] = combined["persons"].apply(persons_display)

    return combined
