"""FOTIA — Clasificación y búsqueda de imágenes.

Punto de entrada de la aplicación.
"""

import logging
import os
import platform
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Workaround: Tk build-number check fails on some macOS 15 builds
if platform.system() == "Darwin":
    os.environ.setdefault("SYSTEM_VERSION_COMPAT", "0")

import customtkinter as ctk

from PIL import Image as PILImage

from modules.database import load_config, save_config, CARAS_DIR, APP_DIR


def _pick_font() -> str:
    """Elige una fuente con personalidad disponible en el sistema."""
    import tkinter.font as tkfont
    # Orden de preferencia: Futura (macOS), Segoe UI Black (Win), Montserrat, Poppins, fallback
    candidates = ["Futura", "Segoe UI Black", "Montserrat", "Poppins", "Century Gothic",
                   "Verdana", "Arial Black", "Helvetica Neue"]
    available = set(tkfont.families())
    for font in candidates:
        if font in available:
            return font
    return "TkDefaultFont"
from modules.recognizer import FaceStore
from modules.ui.tab_analysis import AnalysisTab
from modules.ui.tab_recognition import RecognitionTab
from modules.ui.tab_search import SearchTab

# ── Logging ─────────────────────────────────────────────────────────────

APP_DIR = Path(__file__).resolve().parent
LOG_PATH = APP_DIR / "app.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        RotatingFileHandler(LOG_PATH, maxBytes=5 * 1024 * 1024, backupCount=1, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


# ── Aplicación ──────────────────────────────────────────────────────────

class FotiaApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("FOTIA — Análisis de Imágenes")
        self.geometry("1100x700")
        self.minsize(900, 550)

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # Config
        self.config_data = load_config()

        # Face store
        CARAS_DIR.mkdir(parents=True, exist_ok=True)
        self.face_store = FaceStore()
        self.face_store.load_from_disk()

        self._build_ui()

    def _build_ui(self):
        # ── Header con ajustes ─────────────────────────────────────
        header = ctk.CTkFrame(self, height=40)
        header.pack(fill="x", padx=10, pady=(10, 0))

        # Icono
        icon_path = APP_DIR / "iconoflat.png"
        if icon_path.exists():
            pil_icon = PILImage.open(icon_path)
            self._header_icon = ctk.CTkImage(light_image=pil_icon, size=(32, 32))
            ctk.CTkLabel(header, image=self._header_icon, text="").pack(side="left", padx=(10, 2))

        self._brand_font = _pick_font()
        ctk.CTkLabel(
            header, text="FOTIA", font=ctk.CTkFont(family=self._brand_font, size=24, weight="bold"),
        ).pack(side="left", padx=(2, 10))

        ctk.CTkButton(header, text="Ajustes", width=80, command=self._open_settings).pack(side="right", padx=10)

        # ── Tabs ───────────────────────────────────────────────────
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=10, pady=10)

        tab_search = self.tabview.add("Buscar")
        tab_analysis = self.tabview.add("Análisis")
        tab_recognition = self.tabview.add("Reconocimiento")

        self.search_tab = SearchTab(tab_search, self.config_data)
        self.analysis_tab = AnalysisTab(tab_analysis, self.config_data, self.face_store)
        self.recognition_tab = RecognitionTab(tab_recognition, self.config_data, self.face_store)

        self.tabview.set("Buscar")

    def _open_settings(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Ajustes")
        dialog.geometry("400x420")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()

        # Scrollable por si crece
        frame = ctk.CTkFrame(dialog)
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        # YOLO confidence
        ctk.CTkLabel(frame, text="Confianza YOLO (0.1 - 1.0):").pack(padx=10, pady=(10, 2), anchor="w")
        yolo_slider = ctk.CTkSlider(frame, from_=0.1, to=1.0, number_of_steps=18)
        yolo_slider.set(self.config_data.get("yolo_confidence", 0.4))
        yolo_slider.pack(fill="x", padx=10)
        yolo_val = ctk.CTkLabel(frame, text=f"{yolo_slider.get():.2f}")
        yolo_val.pack(padx=10, anchor="e")
        yolo_slider.configure(command=lambda v: yolo_val.configure(text=f"{v:.2f}"))

        # Face tolerance
        ctk.CTkLabel(frame, text="Tolerancia facial (0.1 - 1.0):  menor = más estricto").pack(padx=10, pady=(10, 2), anchor="w")
        face_slider = ctk.CTkSlider(frame, from_=0.1, to=1.0, number_of_steps=18)
        face_slider.set(self.config_data.get("face_tolerance", 0.6))
        face_slider.pack(fill="x", padx=10)
        face_val = ctk.CTkLabel(frame, text=f"{face_slider.get():.2f}")
        face_val.pack(padx=10, anchor="e")
        face_slider.configure(command=lambda v: face_val.configure(text=f"{v:.2f}"))

        # Min face size
        ctk.CTkLabel(frame, text="Tamaño mínimo de cara (px):").pack(padx=10, pady=(10, 2), anchor="w")
        face_px_slider = ctk.CTkSlider(frame, from_=20, to=120, number_of_steps=20)
        face_px_slider.set(self.config_data.get("min_face_px", 40))
        face_px_slider.pack(fill="x", padx=10)
        face_px_val = ctk.CTkLabel(frame, text=f"{int(face_px_slider.get())} px")
        face_px_val.pack(padx=10, anchor="e")
        face_px_slider.configure(command=lambda v: face_px_val.configure(text=f"{int(v)} px"))

        # Min blur variance
        ctk.CTkLabel(frame, text="Umbral de nitidez (menor = acepta más borrosas):").pack(padx=10, pady=(10, 2), anchor="w")
        blur_slider = ctk.CTkSlider(frame, from_=1, to=80, number_of_steps=16)
        blur_slider.set(self.config_data.get("min_blur_var", 15.0))
        blur_slider.pack(fill="x", padx=10)
        blur_val = ctk.CTkLabel(frame, text=f"{blur_slider.get():.0f}")
        blur_val.pack(padx=10, anchor="e")
        blur_slider.configure(command=lambda v: blur_val.configure(text=f"{v:.0f}"))

        def _save():
            self.config_data["yolo_confidence"] = round(yolo_slider.get(), 2)
            self.config_data["face_tolerance"] = round(face_slider.get(), 2)
            self.config_data["min_face_px"] = int(face_px_slider.get())
            self.config_data["min_blur_var"] = round(blur_slider.get(), 1)
            save_config(self.config_data)
            dialog.destroy()

        ctk.CTkButton(frame, text="Guardar", command=_save).pack(pady=15)


def main():
    logger.info("Iniciando FOTIA")
    app = FotiaApp()
    app.mainloop()


if __name__ == "__main__":
    main()
