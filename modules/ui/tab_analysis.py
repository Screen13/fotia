"""Pestaña 1 — Análisis de imágenes."""

import logging
import threading
import time
from datetime import datetime
from pathlib import Path

import customtkinter as ctk
import pandas as pd

from modules import database, analyzer, recognizer as rec_module

logger = logging.getLogger(__name__)


class AnalysisTab:
    def __init__(self, parent: ctk.CTkFrame, config: dict, face_store: rec_module.FaceStore):
        self.parent = parent
        self.config = config
        self.face_store = face_store
        self._cancel = False
        self._running = False

        self._build_ui()

    def _build_ui(self):
        # ── Selección de carpeta ────────────────────────────────────
        folder_frame = ctk.CTkFrame(self.parent)
        folder_frame.pack(fill="x", padx=10, pady=(10, 5))

        ctk.CTkButton(folder_frame, text="Seleccionar carpeta base", command=self._select_folder).pack(side="left", padx=5)

        self.folder_label = ctk.CTkLabel(
            folder_frame,
            text=self.config.get("base_folder") or "(sin carpeta seleccionada)",
            anchor="w",
        )
        self.folder_label.pack(side="left", fill="x", expand=True, padx=10)

        # ── Controles ──────────────────────────────────────────────
        ctrl_frame = ctk.CTkFrame(self.parent)
        ctrl_frame.pack(fill="x", padx=10, pady=5)

        self.btn_analyze = ctk.CTkButton(ctrl_frame, text="Iniciar Análisis", command=self._start_analysis)
        self.btn_analyze.pack(fill="x", padx=5)

        self.btn_cancel = ctk.CTkButton(
            ctrl_frame, text="Cancelar", command=self._cancel_analysis,
            fg_color="#aa0000", hover_color="#770000",
        )
        # Cancelar empieza oculto
        self.btn_cancel.pack_forget()

        # ── Progreso ───────────────────────────────────────────────
        prog_frame = ctk.CTkFrame(self.parent)
        prog_frame.pack(fill="x", padx=10, pady=5)

        self.progress_bar = ctk.CTkProgressBar(prog_frame)
        self.progress_bar.pack(fill="x", padx=5, pady=5)
        self.progress_bar.set(0)

        self.progress_label = ctk.CTkLabel(prog_frame, text="Listo", anchor="w")
        self.progress_label.pack(fill="x", padx=5)

        # ── Log ────────────────────────────────────────────────────
        self.log_text = ctk.CTkTextbox(self.parent, height=300, state="disabled")
        self.log_text.pack(fill="both", expand=True, padx=10, pady=(5, 10))

    def _select_folder(self):
        from tkinter import filedialog
        path = filedialog.askdirectory(title="Seleccionar carpeta base de imágenes")
        if path:
            self.config["base_folder"] = path
            database.save_config(self.config)
            self.folder_label.configure(text=path)
            self._log(f"Carpeta base: {path}")

    def _log(self, msg: str):
        def _update():
            self.log_text.configure(state="normal")
            self.log_text.insert("end", f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n")
            self.log_text.see("end")
            self.log_text.configure(state="disabled")
        self.parent.after(0, _update)

    def _set_progress(self, value: float, text: str):
        def _update():
            self.progress_bar.set(value)
            self.progress_label.configure(text=text)
        self.parent.after(0, _update)

    def _set_buttons(self, running: bool):
        def _update():
            if running:
                self.btn_analyze.pack_forget()
                self.btn_cancel.pack(fill="x", padx=5)
            else:
                self.btn_cancel.pack_forget()
                self.btn_analyze.pack(fill="x", padx=5)
        self.parent.after(0, _update)

    def _cancel_analysis(self):
        self._cancel = True
        self._log("Cancelando...")

    def _start_analysis(self, force: bool = False):
        base = self.config.get("base_folder", "")
        if not base or not Path(base).is_dir():
            self._log("ERROR: Selecciona una carpeta base válida primero.")
            return
        if self._running:
            return

        self._running = True
        self._cancel = False
        self._set_buttons(True)

        thread = threading.Thread(target=self._run_analysis, args=(base, force), daemon=True)
        thread.start()

    def _run_analysis(self, base_folder: str, force: bool):
        try:
            self._log("Escaneando carpeta...")
            db, new_images = database.sync_database(base_folder, force=force)

            total = len(new_images)
            if total == 0:
                self._log("No hay imágenes nuevas por procesar.")
                if not force:
                    database.save_database(base_folder, db)
                self._set_progress(1.0, "Completado — sin imágenes nuevas")
                return

            self._log(f"Imágenes a procesar: {total}")
            self._log("Cargando modelos...")

            conf = self.config.get("yolo_confidence", 0.4)
            tol = self.config.get("face_tolerance", 0.6)
            min_face_px = self.config.get("min_face_px", 40)
            min_blur_var = self.config.get("min_blur_var", 15.0)

            rows = []
            for i, img_path in enumerate(new_images):
                if self._cancel:
                    self._log("Análisis cancelado por el usuario.")
                    break

                rel = str(img_path.relative_to(base_folder))
                self._set_progress((i + 1) / total, f"{i + 1}/{total} — {img_path.name}")

                # Detección de objetos
                try:
                    tags = analyzer.detect_objects(str(img_path), confidence=conf)
                except Exception as e:
                    logger.error("YOLO error en %s: %s", rel, e)
                    tags = []

                # Detección facial
                person_fps = []
                try:
                    faces = analyzer.detect_faces(str(img_path), min_face_px=min_face_px, min_blur_var=min_blur_var)
                    for encoding, location in faces:
                        fp = analyzer.match_face(encoding, self.face_store.encodings, tolerance=tol)
                        if fp is None:
                            fp = database.new_fingerprint()
                        self.face_store.add_encoding(fp, encoding)

                        # Guardar recorte
                        face_dir = database.CARAS_DIR / fp
                        face_dir.mkdir(parents=True, exist_ok=True)
                        crop_name = f"{fp}_{int(time.time() * 1000)}.jpg"
                        analyzer.crop_face(str(img_path), location, str(face_dir / crop_name))

                        person_fps.append(fp)
                except Exception as e:
                    logger.error("Face detection error en %s: %s", rel, e)

                rows.append({
                    "filename": img_path.name,
                    "rel_path": rel,
                    "tags": "|".join(tags),
                    "persons": "|".join(person_fps),
                })

                if (i + 1) % 10 == 0:
                    self._log(f"  Procesadas {i + 1}/{total}")

            # Guardar resultados
            if rows:
                new_df = pd.DataFrame(rows)
                db = pd.concat([db, new_df], ignore_index=True)

            database.save_database(base_folder, db)
            self.face_store.save_to_disk()

            self.config["last_analysis"] = datetime.now().isoformat()
            database.save_config(self.config)

            processed = len(rows)
            self._log(f"Análisis completado: {processed} imágenes procesadas.")
            self._set_progress(1.0, f"Completado — {processed} imágenes procesadas")

        except Exception as e:
            logger.exception("Error durante análisis")
            self._log(f"ERROR: {e}")
        finally:
            self._running = False
            self._set_buttons(False)
