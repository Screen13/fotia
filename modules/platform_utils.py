"""Utilidades multiplataforma."""

import os
import platform
import subprocess
import logging

logger = logging.getLogger(__name__)

SYSTEM = platform.system()


def open_file(path: str):
    """Abre un archivo con la aplicación predeterminada del SO."""
    try:
        if SYSTEM == "Darwin":
            subprocess.Popen(["open", path])
        elif SYSTEM == "Windows":
            os.startfile(path)
        else:
            subprocess.Popen(["xdg-open", path])
    except Exception as e:
        logger.error("Error abriendo archivo %s: %s", path, e)


def show_in_explorer(path: str):
    """Abre el explorador de archivos y selecciona el archivo."""
    try:
        if SYSTEM == "Darwin":
            subprocess.Popen(["open", "-R", path])
        elif SYSTEM == "Windows":
            subprocess.Popen(["explorer", "/select,", path])
        else:
            # Linux: abrir la carpeta contenedora
            parent = os.path.dirname(path)
            subprocess.Popen(["xdg-open", parent])
    except Exception as e:
        logger.error("Error mostrando en explorador %s: %s", path, e)


def bind_right_click(widget, callback):
    """Bindea clic derecho en un widget, compatible con macOS/Win/Linux."""
    widget.bind("<Button-2>", callback)
    widget.bind("<Button-3>", callback)
    if SYSTEM == "Darwin":
        widget.bind("<Control-Button-1>", callback)
