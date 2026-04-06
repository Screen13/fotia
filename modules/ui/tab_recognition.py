"""Pestaña 2 — Reconocimiento y gestión de personas."""

import logging
from pathlib import Path
from typing import Optional

import customtkinter as ctk
from PIL import Image

from modules import database, recognizer as rec_module

logger = logging.getLogger(__name__)

THUMB_SIZE = 100


class RecognitionTab:
    def __init__(self, parent: ctk.CTkFrame, config: dict, face_store: rec_module.FaceStore):
        self.parent = parent
        self.config = config
        self.face_store = face_store
        self.selected_fp = None   # type: Optional[str]
        self._thumb_refs = []     # Keep references to prevent GC
        self._fp_order = []       # Lista ordenada de fingerprints visibles
        self._fp_names = {}       # Cache {fingerprint: nombre}
        self._row_widgets = {}    # {fingerprint: frame_widget} para highlight

        self._build_ui()
        self.refresh_list()

    def _build_ui(self):
        # ── Layout principal: izquierda (lista) + derecha (detalle) ─
        container = ctk.CTkFrame(self.parent)
        container.pack(fill="both", expand=True, padx=10, pady=10)
        container.grid_columnconfigure(0, weight=1)
        container.grid_columnconfigure(1, weight=3)
        container.grid_rowconfigure(0, weight=1)

        # Panel izquierdo — lista de fingerprints
        left = ctk.CTkFrame(container)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 5))

        ctk.CTkLabel(left, text="Personas detectadas", font=ctk.CTkFont(size=14, weight="bold")).pack(padx=5, pady=5)

        # Header de columnas
        header = ctk.CTkFrame(left, fg_color="transparent")
        header.pack(fill="x", padx=5)
        ctk.CTkLabel(header, text="", width=28, font=ctk.CTkFont(size=11)).pack(side="left", padx=(2, 0))
        ctk.CTkLabel(header, text="Nombre", width=120, anchor="w", font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=2)
        ctk.CTkLabel(header, text="Fingerprint", anchor="w", font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=2)

        self.fp_list_frame = ctk.CTkScrollableFrame(left)
        self.fp_list_frame.pack(fill="both", expand=True, padx=5, pady=5)

        btn_refresh = ctk.CTkButton(left, text="Actualizar lista", command=self.refresh_list)
        btn_refresh.pack(padx=5, pady=5)

        # Panel derecho — detalle
        right = ctk.CTkFrame(container)
        right.grid(row=0, column=1, sticky="nsew", padx=(5, 0))

        self.detail_label = ctk.CTkLabel(
            right, text="Selecciona una persona de la lista",
            font=ctk.CTkFont(size=14),
        )
        self.detail_label.pack(padx=10, pady=10)

        # Grid de miniaturas
        self.thumbs_frame = ctk.CTkScrollableFrame(right, height=350)
        self.thumbs_frame.pack(fill="both", expand=True, padx=10, pady=5)

        # ── Nombre + Fusionar (grid alineado) ──────────────────────
        form_frame = ctk.CTkFrame(right)
        form_frame.pack(fill="x", padx=10, pady=(5, 10))
        form_frame.grid_columnconfigure(1, weight=1)  # columna central se expande

        LABEL_W = 100
        BTN_W = 90

        # Fila 1: Nombre
        ctk.CTkLabel(form_frame, text="Nombre:", width=LABEL_W, anchor="w").grid(
            row=0, column=0, padx=(5, 5), pady=5, sticky="w")
        self.name_entry = ctk.CTkEntry(form_frame)
        self.name_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        ctk.CTkButton(form_frame, text="Guardar", width=BTN_W,
                       command=self._save_name).grid(row=0, column=2, padx=(5, 5), pady=5)

        # Bind flechas arriba/abajo en el campo de nombre
        self.name_entry.bind("<Up>", lambda e: self._move_selection(-1))
        self.name_entry.bind("<Down>", lambda e: self._move_selection(1))

        # Fila 2: Fusionar
        ctk.CTkLabel(form_frame, text="Fusionar con:", width=LABEL_W, anchor="w").grid(
            row=1, column=0, padx=(5, 5), pady=5, sticky="w")
        self.merge_combo = ctk.CTkComboBox(form_frame, values=[])
        self.merge_combo.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        ctk.CTkButton(form_frame, text="Fusionar", width=BTN_W,
                       command=self._merge,
                       fg_color="#cc5500", hover_color="#993d00").grid(
            row=1, column=2, padx=(5, 5), pady=5)

    # ── Lista de personas ───────────────────────────────────────────

    def refresh_list(self):
        # Limpiar lista
        for w in self.fp_list_frame.winfo_children():
            w.destroy()
        self._row_widgets.clear()

        fps = self.face_store.get_all_fingerprints()
        personas = database.load_personas()
        self._fp_names = {}
        if not personas.empty:
            for _, row in personas.iterrows():
                self._fp_names[row["fingerprint"]] = row["nombre"]

        # Ordenar: con nombre primero (alfabético), sin nombre después
        def sort_key(fp):
            name = self._fp_names.get(fp, "")
            if name:
                return (0, name.lower(), fp)
            return (1, "", fp)

        fps_sorted = sorted(fps, key=sort_key)
        self._fp_order = fps_sorted

        for fp in fps_sorted:
            name = self._fp_names.get(fp, "")
            has_entry = fp in self._fp_names  # Existe en personas.csv
            has_name = bool(name)

            row_frame = ctk.CTkFrame(self.fp_list_frame, cursor="hand2")
            row_frame.pack(fill="x", padx=2, pady=1)
            self._row_widgets[fp] = row_frame

            # Columna 1: indicador de estado
            if has_name:
                indicator = ctk.CTkLabel(row_frame, text="✅", width=28, font=ctk.CTkFont(size=13))
            elif has_entry:
                # Guardado pero nombre vacío
                indicator = ctk.CTkLabel(row_frame, text="❌", width=28, font=ctk.CTkFont(size=13))
            else:
                indicator = ctk.CTkLabel(row_frame, text="·", width=28,
                                         text_color="gray50", font=ctk.CTkFont(size=13))
            indicator.pack(side="left", padx=(2, 0))

            # Columna 2: nombre
            name_display = name if name else "—"
            name_color = ("gray10", "gray90") if name else ("gray50", "gray60")
            name_lbl = ctk.CTkLabel(row_frame, text=name_display, width=120, anchor="w",
                                     text_color=name_color, font=ctk.CTkFont(size=12))
            name_lbl.pack(side="left", padx=2)

            # Columna 3: fingerprint (corto)
            fp_lbl = ctk.CTkLabel(row_frame, text=fp[:12] + "…", anchor="w",
                                   text_color=("gray40", "gray60"), font=ctk.CTkFont(size=11))
            fp_lbl.pack(side="left", padx=2)

            # Click en cualquier parte de la fila
            for widget in [row_frame, indicator, name_lbl, fp_lbl]:
                widget.bind("<Button-1>", lambda e, f=fp: self._select_fingerprint(f))
                widget.configure(cursor="hand2")

        self._update_merge_combo()
        self._highlight_selected()

    def _highlight_selected(self):
        """Resalta la fila seleccionada."""
        for fp, frame in self._row_widgets.items():
            if fp == self.selected_fp:
                frame.configure(fg_color=("gray75", "gray35"))
            else:
                frame.configure(fg_color="transparent")

    # ── Combo de fusión ─────────────────────────────────────────────

    def _update_merge_combo(self):
        fps = self.face_store.get_all_fingerprints()
        values = []
        for fp in fps:
            if fp == self.selected_fp:
                continue
            name = self._fp_names.get(fp, "")
            if name:
                display = f"{name} ({fp[:8]})"
            else:
                display = fp[:16]
            values.append(f"{fp}||{display}")

        display_values = [v.split("||")[1] for v in values]
        self._merge_map = {v.split("||")[1]: v.split("||")[0] for v in values}
        self.merge_combo.configure(values=display_values)
        if display_values:
            self.merge_combo.set(display_values[0])

    # ── Selección y navegación ──────────────────────────────────────

    def _auto_save_current(self):
        """Guarda automáticamente el nombre de la persona actual si cambió."""
        if not self.selected_fp:
            return
        new_name = self.name_entry.get().strip()
        old_name = self._fp_names.get(self.selected_fp, "")
        if new_name != old_name:
            database.set_persona_name(self.selected_fp, new_name)
            self._fp_names[self.selected_fp] = new_name
            logger.info("Auto-guardado nombre '%s' para %s", new_name, self.selected_fp[:12])
            # Actualizar la fila en la lista sin reconstruir todo
            self._refresh_row(self.selected_fp)

    def _refresh_row(self, fp: str):
        """Actualiza visualmente una fila individual."""
        if fp not in self._row_widgets:
            return
        frame = self._row_widgets[fp]
        children = frame.winfo_children()
        if len(children) < 3:
            return

        name = self._fp_names.get(fp, "")
        has_entry = fp in self._fp_names
        has_name = bool(name)

        # Actualizar indicador
        if has_name:
            children[0].configure(text="✅")
        elif has_entry:
            children[0].configure(text="❌")
        else:
            children[0].configure(text="·")

        # Actualizar nombre
        children[1].configure(
            text=name if name else "—",
            text_color=("gray10", "gray90") if name else ("gray50", "gray60"),
        )

    def _select_fingerprint(self, fp: str):
        # Auto-guardar la persona actual antes de cambiar
        self._auto_save_current()

        self.selected_fp = fp
        name = self._fp_names.get(fp, "")

        self.detail_label.configure(text=f"Fingerprint: {fp[:16]}…")
        self.name_entry.delete(0, "end")
        if name:
            self.name_entry.insert(0, name)

        self._highlight_selected()
        self._load_thumbnails(fp)
        self._update_merge_combo()

        # Foco en el campo de nombre
        self.name_entry.focus_set()

    def _move_selection(self, direction: int):
        """Mueve la selección arriba (-1) o abajo (+1) en la lista."""
        if not self._fp_order:
            return "break"

        if self.selected_fp and self.selected_fp in self._fp_order:
            idx = self._fp_order.index(self.selected_fp)
            new_idx = idx + direction
        else:
            new_idx = 0

        # Clamp
        new_idx = max(0, min(new_idx, len(self._fp_order) - 1))
        new_fp = self._fp_order[new_idx]

        if new_fp != self.selected_fp:
            self._select_fingerprint(new_fp)
            # Scroll para que la fila sea visible
            if new_fp in self._row_widgets:
                self._row_widgets[new_fp].update_idletasks()

        return "break"  # Evitar comportamiento por defecto de la flecha en el Entry

    # ── Miniaturas ──────────────────────────────────────────────────

    def _load_thumbnails(self, fp: str):
        for w in self.thumbs_frame.winfo_children():
            w.destroy()
        self._thumb_refs.clear()

        images = self.face_store.get_face_images(fp, limit=50)
        if not images:
            ctk.CTkLabel(self.thumbs_frame, text="Sin recortes de cara").pack()
            return

        cols = 6
        for i, img_path in enumerate(images):
            try:
                pil_img = Image.open(img_path)
                pil_img.thumbnail((THUMB_SIZE, THUMB_SIZE))
                ctk_img = ctk.CTkImage(light_image=pil_img, size=(THUMB_SIZE, THUMB_SIZE))
                self._thumb_refs.append(ctk_img)

                lbl = ctk.CTkLabel(self.thumbs_frame, image=ctk_img, text="")
                lbl.grid(row=i // cols, column=i % cols, padx=3, pady=3)
            except Exception as e:
                logger.warning("No se pudo cargar miniatura %s: %s", img_path, e)

    # ── Guardar nombre ──────────────────────────────────────────────

    def _save_name(self):
        if not self.selected_fp:
            return
        name = self.name_entry.get().strip()
        database.set_persona_name(self.selected_fp, name)
        self._fp_names[self.selected_fp] = name
        self._refresh_row(self.selected_fp)
        self._update_merge_combo()
        logger.info("Nombre '%s' asignado a %s", name, self.selected_fp[:12])

    # ── Fusionar ────────────────────────────────────────────────────

    def _merge(self):
        if not self.selected_fp:
            return

        display = self.merge_combo.get()
        if not display or display not in self._merge_map:
            return

        remove_fp = self._merge_map[display]
        keep_fp = self.selected_fp
        base = self.config.get("base_folder", "")

        from tkinter import messagebox
        ok = messagebox.askyesno(
            "Confirmar fusión",
            f"¿Fusionar '{display}' en el fingerprint seleccionado?\n\n"
            f"Se conserva: {keep_fp[:16]}…\n"
            f"Se elimina: {remove_fp[:16]}…\n\n"
            "Esta acción no se puede deshacer.",
        )
        if not ok:
            return

        database.merge_fingerprints(keep_fp, remove_fp, base)
        self.face_store.merge(keep_fp, remove_fp)
        self.refresh_list()
        self._select_fingerprint(keep_fp)
        logger.info("Fusión completada: %s → %s", remove_fp[:12], keep_fp[:12])
