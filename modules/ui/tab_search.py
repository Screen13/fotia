"""Pestaña 3 — Búsqueda de imágenes."""

import logging
import threading
from pathlib import Path

import customtkinter as ctk
from PIL import Image

from modules import searcher, database
from modules.platform_utils import open_file, show_in_explorer, bind_right_click

logger = logging.getLogger(__name__)

THUMB_SIZE = 30


class SearchTab:
    def __init__(self, parent: ctk.CTkFrame, config: dict):
        self.parent = parent
        self.config = config
        self._thumb_refs = []

        self._build_ui()

    def _build_ui(self):
        # ── Barra de búsqueda ──────────────────────────────────────
        search_frame = ctk.CTkFrame(self.parent)
        search_frame.pack(fill="x", padx=10, pady=(10, 5))

        self.search_entry = ctk.CTkEntry(search_frame, placeholder_text="Buscar por etiqueta o nombre de persona...")
        self.search_entry.pack(side="left", fill="x", expand=True, padx=(5, 0))
        self.search_entry.bind("<Return>", lambda e: self._do_search())
        # CTkEntry a veces no propaga bind; forzar en el widget interno de tk
        try:
            self.search_entry._entry.bind("<Return>", lambda e: self._do_search())
        except AttributeError:
            pass

        ctk.CTkButton(search_frame, text="✕", width=28, fg_color="transparent",
                       text_color=("gray40", "gray60"), hover_color=("gray80", "gray30"),
                       command=self._clear_search).pack(side="left", padx=(0, 2))

        ctk.CTkButton(search_frame, text="Buscar", width=80, command=self._do_search).pack(side="left", padx=5)

        # Desplegable de etiquetas
        self._tags_placeholder = "(etiquetas)"
        self.tags_combo = ctk.CTkComboBox(search_frame, width=140, values=[self._tags_placeholder],
                                           command=self._on_tag_selected)
        self.tags_combo.pack(side="left", padx=(10, 5))
        self.tags_combo.set(self._tags_placeholder)

        # Desplegable de personas
        self._persons_placeholder = "(personas)"
        self.persons_combo = ctk.CTkComboBox(search_frame, width=140, values=[self._persons_placeholder],
                                              command=self._on_person_selected)
        self.persons_combo.pack(side="left", padx=(5, 5))
        self.persons_combo.set(self._persons_placeholder)

        # Cargar valores iniciales
        self._refresh_combos()

        self.result_label = ctk.CTkLabel(self.parent, text="", anchor="w")
        self.result_label.pack(fill="x", padx=15, pady=(0, 5))

        # ── Tabla de resultados ────────────────────────────────────
        # Header
        header_frame = ctk.CTkFrame(self.parent)
        header_frame.pack(fill="x", padx=10)

        headers = [("", 40), ("Archivo", 180), ("Ruta relativa", 250), ("Etiquetas", 200), ("Personas", 180)]
        for text, width in headers:
            ctk.CTkLabel(
                header_frame, text=text, width=width, anchor="w",
                font=ctk.CTkFont(size=12, weight="bold"),
            ).pack(side="left", padx=2)

        # Resultados scrollable
        self.results_frame = ctk.CTkScrollableFrame(self.parent)
        self.results_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    def _clear_search(self):
        self.search_entry.delete(0, "end")
        self.search_entry.focus_set()

    def _refresh_combos(self):
        """Carga etiquetas y personas únicas en los desplegables."""
        base = self.config.get("base_folder", "")
        # Etiquetas
        tags = set()
        if base:
            db = database.load_database(base)
            if not db.empty:
                for val in db["tags"].dropna():
                    for t in val.split("|"):
                        t = t.strip()
                        if t:
                            tags.add(t)
        tag_list = sorted(tags) if tags else ["(sin etiquetas)"]
        self.tags_combo.configure(values=tag_list)
        self.tags_combo.set(tag_list[0])

        # Personas con nombre
        personas = database.load_personas()
        names = []
        if not personas.empty:
            for _, row in personas.iterrows():
                if row["nombre"].strip():
                    names.append(row["nombre"].strip())
        names = sorted(set(names), key=str.lower) if names else ["(sin personas)"]
        self.persons_combo.configure(values=names)
        self.persons_combo.set(names[0])

    def _on_tag_selected(self, val: str):
        if val and val != self._tags_placeholder:
            current = self.search_entry.get()
            self.search_entry.delete(0, "end")
            self.search_entry.insert(0, current + val + " ")
            self.search_entry.focus_set()
        self.tags_combo.set(self._tags_placeholder)

    def _on_person_selected(self, val: str):
        if val and val != self._persons_placeholder:
            current = self.search_entry.get()
            self.search_entry.delete(0, "end")
            self.search_entry.insert(0, current + val + " ")
            self.search_entry.focus_set()
        self.persons_combo.set(self._persons_placeholder)

    def _do_search(self):
        self._refresh_combos()
        query = self.search_entry.get().strip()
        base = self.config.get("base_folder", "")
        logger.info("Búsqueda: query='%s', base='%s'", query, base)
        if not base:
            self.result_label.configure(text="Selecciona una carpeta base primero (pestaña Análisis).")
            return
        if not query:
            self.result_label.configure(text="Escribe un término de búsqueda.")
            return

        # Limpiar resultados anteriores
        for w in self.results_frame.winfo_children():
            w.destroy()
        self._thumb_refs.clear()
        self.result_label.configure(text="Buscando...")

        # Ejecutar búsqueda en hilo para UIs con datasets grandes
        def _search():
            try:
                results = searcher.search(base, query)
                logger.info("Búsqueda completada: %d resultados", len(results))
                self.parent.after(0, lambda: self._display_results(results, query))
            except Exception as e:
                logger.error("Error en búsqueda: %s", e)
                self.parent.after(0, lambda: self.result_label.configure(text=f"Error: {e}"))

        threading.Thread(target=_search, daemon=True).start()

    def _display_results(self, df, query: str):
        if df.empty:
            self.result_label.configure(text=f"Sin resultados para '{query}'")
            return

        self.result_label.configure(text=f"{len(df)} resultado(s) para '{query}'")
        base = Path(self.config["base_folder"])
        self._selected_row = None

        for idx, row in df.iterrows():
            row_frame = ctk.CTkFrame(self.results_frame, fg_color="transparent")
            row_frame.pack(fill="x", padx=2, pady=1)

            full_path = base / row["rel_path"]

            # Miniatura
            thumb_label = ctk.CTkLabel(row_frame, text="", width=40)
            try:
                pil_img = Image.open(full_path)
                pil_img.thumbnail((THUMB_SIZE, THUMB_SIZE))
                ctk_img = ctk.CTkImage(light_image=pil_img, size=(THUMB_SIZE, THUMB_SIZE))
                self._thumb_refs.append(ctk_img)
                thumb_label.configure(image=ctk_img)
            except Exception:
                thumb_label.configure(text="?")
            thumb_label.pack(side="left", padx=2)

            # Columnas de texto
            ctk.CTkLabel(row_frame, text=row["filename"], width=180, anchor="w").pack(side="left", padx=2)
            ctk.CTkLabel(row_frame, text=row["rel_path"], width=250, anchor="w").pack(side="left", padx=2)

            tags_display = row["tags"].replace("|", ", ") if row["tags"] else ""
            ctk.CTkLabel(row_frame, text=tags_display, width=200, anchor="w").pack(side="left", padx=2)

            persons = row.get("persons_display", "")
            ctk.CTkLabel(row_frame, text=persons, width=180, anchor="w").pack(side="left", padx=2)

            # Bind clic, doble clic y clic derecho
            for widget in [row_frame] + row_frame.winfo_children():
                widget.bind("<Button-1>", lambda e, f=row_frame: self._highlight_row(f))
                widget.bind("<Double-Button-1>", lambda e, p=full_path: self._open_image(p))
                bind_right_click(widget, lambda e, p=full_path: self._context_menu(e, p))

    def _highlight_row(self, row_frame):
        if self._selected_row is not None:
            self._selected_row.configure(fg_color="transparent")
        row_frame.configure(fg_color=("gray75", "gray35"))
        self._selected_row = row_frame

    def _open_image(self, path: Path):
        open_file(str(path))

    def _show_in_explorer(self, path: Path):
        show_in_explorer(str(path))

    def _copy_path(self, path: Path):
        self.parent.clipboard_clear()
        self.parent.clipboard_append(str(path))

    def _context_menu(self, event, path: Path):
        from tkinter import Menu
        menu = Menu(self.parent, tearoff=0)
        menu.add_command(label="Abrir imagen", command=lambda: self._open_image(path))
        menu.add_command(label="Mostrar en explorador", command=lambda: self._show_in_explorer(path))
        menu.add_command(label="Copiar ruta", command=lambda: self._copy_path(path))
        menu.tk_popup(event.x_root, event.y_root)
