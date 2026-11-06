from __future__ import annotations

import tkinter as tk
from tkinter import scrolledtext, ttk
from typing import Any

from .app_theme import theme_colors


def shell_style_spacing(compact_mode: bool) -> dict[str, tuple[int, int]]:
    if compact_mode:
        return {"button_padding": (10, 5), "accent_padding": (12, 6), "tab_padding": (14, 7)}
    return {"button_padding": (12, 7), "accent_padding": (14, 8), "tab_padding": (18, 10)}


class DamienShellBuilder:
    def __init__(self, app: Any) -> None:
        self.app = app

    def style(self) -> None:
        app = self.app
        style = ttk.Style(app)
        style.theme_use("clam")
        app.colors = self.theme_colors()
        app.configure(bg=app.colors["bg"])
        style.configure("TFrame", background=app.colors["bg"])
        style.configure("Panel.TFrame", background=app.colors["panel"])
        style.configure("Sidebar.TFrame", background=app.colors["panel_deep"])
        style.configure("Topbar.TFrame", background=app.colors["panel"])
        style.configure("Surface.TFrame", background=app.colors["panel_alt"])
        style.configure("TLabel", background=app.colors["bg"], foreground=app.colors["text"], font=("Segoe UI", 10))
        style.configure("Panel.TLabel", background=app.colors["panel"], foreground=app.colors["text"], font=("Segoe UI", 10))
        style.configure("Muted.TLabel", background=app.colors["bg"], foreground=app.colors["muted"], font=("Segoe UI", 9))
        style.configure("PanelMuted.TLabel", background=app.colors["panel"], foreground=app.colors["muted"], font=("Segoe UI", 9))
        style.configure("Title.TLabel", background=app.colors["bg"], foreground=app.colors["text"], font=("Segoe UI", 24, "bold"))
        style.configure("SectionTitle.TLabel", background=app.colors["panel"], foreground=app.colors["text"], font=("Segoe UI", 12, "bold"))
        style.configure("Brand.TLabel", background=app.colors["panel_deep"], foreground=app.colors["text"], font=("Segoe UI", 19, "bold"))
        style.configure("Eyebrow.TLabel", background=app.colors["panel_deep"], foreground=app.colors["accent"], font=("Segoe UI", 8, "bold"))
        style.configure("Nav.TButton", background=app.colors["panel_deep"], foreground=app.colors["muted"], anchor="w", padding=(14, 11), font=("Segoe UI", 10, "bold"), borderwidth=0)
        style.map("Nav.TButton", background=[("active", app.colors["panel_alt"])], foreground=[("active", app.colors["text"])])
        style.configure("NavActive.TButton", background=app.colors["accent_dark"], foreground="#ffffff", anchor="w", padding=(14, 11), font=("Segoe UI", 10, "bold"), borderwidth=0)
        style.map("NavActive.TButton", background=[("active", app.colors["accent_dark"])], foreground=[("active", "#ffffff")])
        spacing = shell_style_spacing(app.settings.compact_mode)
        style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"), padding=spacing["accent_padding"])
        style.configure("TButton", font=("Segoe UI", 10), padding=spacing["button_padding"])
        style.configure("TCheckbutton", background=app.colors["panel"], foreground=app.colors["text"], font=("Segoe UI", 10))
        style.map("TCheckbutton", background=[("active", app.colors["panel"])], foreground=[("disabled", app.colors["muted"])])
        style.configure(
            "TEntry",
            padding=(10, 8),
            fieldbackground=app.colors["input_bg"],
            foreground=app.colors["input_text"],
            insertcolor=app.colors["input_text"],
            background=app.colors["input_bg"],
            bordercolor=app.colors["line"],
            lightcolor=app.colors["line"],
            darkcolor=app.colors["line"],
        )
        style.map(
            "TEntry",
            fieldbackground=[
                ("disabled", app.colors["panel_deep"]),
                ("readonly", app.colors["input_bg"]),
                ("!disabled", app.colors["input_bg"]),
            ],
            foreground=[
                ("disabled", app.colors["muted"]),
                ("readonly", app.colors["input_text"]),
                ("!disabled", app.colors["input_text"]),
            ],
            insertcolor=[("!disabled", app.colors["input_text"])],
        )
        style.configure(
            "TCombobox",
            padding=(8, 6),
            fieldbackground=app.colors["input_bg"],
            foreground=app.colors["input_text"],
            background=app.colors["input_bg"],
            arrowcolor=app.colors["text"],
            bordercolor=app.colors["line"],
            lightcolor=app.colors["line"],
            darkcolor=app.colors["line"],
            selectbackground=app.colors["input_bg"],
            selectforeground=app.colors["input_text"],
        )
        style.map(
            "TCombobox",
            fieldbackground=[
                ("disabled", app.colors["panel_deep"]),
                ("readonly", app.colors["input_bg"]),
                ("!disabled", app.colors["input_bg"]),
            ],
            foreground=[
                ("disabled", app.colors["muted"]),
                ("readonly", app.colors["input_text"]),
                ("!disabled", app.colors["input_text"]),
            ],
            background=[
                ("active", app.colors["panel_alt"]),
                ("readonly", app.colors["input_bg"]),
                ("!disabled", app.colors["input_bg"]),
            ],
            arrowcolor=[
                ("disabled", app.colors["muted"]),
                ("!disabled", app.colors["text"]),
            ],
            selectbackground=[("readonly", app.colors["input_bg"]), ("!disabled", app.colors["input_bg"])],
            selectforeground=[("readonly", app.colors["input_text"]), ("!disabled", app.colors["input_text"])],
        )
        app.option_add("*TCombobox*Listbox.background", app.colors["input_bg"])
        app.option_add("*TCombobox*Listbox.foreground", app.colors["input_text"])
        app.option_add("*TCombobox*Listbox.selectBackground", app.colors["accent_dark"])
        app.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")
        style.layout("App.TNotebook", [("Notebook.client", {"sticky": "nswe"})])
        style.layout("App.TNotebook.Tab", [])
        style.configure("App.TNotebook", background=app.colors["bg"], borderwidth=0, tabmargins=0)
        style.configure("TNotebook.Tab", padding=spacing["tab_padding"], font=("Segoe UI", 10, "bold"))

    def theme_colors(self) -> dict[str, str]:
        return theme_colors(self.app.settings)

    def status_card(self, parent: tk.Misc, title: str, variable: tk.StringVar, accent: str) -> tk.Frame:
        app = self.app
        card = tk.Frame(parent, bg=app.colors["panel_deep"], padx=12, pady=10, highlightthickness=1, highlightbackground=app.colors["line"])
        marker = tk.Frame(card, bg=accent, width=4)
        marker.grid(row=0, column=0, rowspan=2, sticky="ns", padx=(0, 10))
        tk.Label(
            card,
            text=title,
            bg=app.colors["panel_deep"],
            fg=app.colors["muted"],
            font=("Segoe UI", 8, "bold"),
            anchor="w",
        ).grid(row=0, column=1, sticky="ew")
        tk.Label(
            card,
            textvariable=variable,
            bg=app.colors["panel_deep"],
            fg=app.colors["text"],
            font=("Segoe UI", 10, "bold"),
            anchor="w",
            justify="left",
            wraplength=220,
        ).grid(row=1, column=1, sticky="ew", pady=(3, 0))
        card.columnconfigure(1, weight=1)
        return card

    def text_surface(
        self,
        parent: tk.Misc,
        font: tuple[str, int] | tuple[str, int, str] = ("Segoe UI", 10),
    ) -> scrolledtext.ScrolledText:
        app = self.app
        surface = scrolledtext.ScrolledText(
            parent,
            wrap=tk.WORD,
            state="disabled",
            padx=16,
            pady=16,
            bg=app.colors["surface_bg"],
            fg=app.colors["surface_text"],
            insertbackground=app.colors["surface_text"],
            relief=tk.FLAT,
            borderwidth=0,
            font=font,
        )
        app.text_surfaces.append(surface)
        return surface

    def scrollable_frame(self, parent: tk.Misc) -> ttk.Frame:
        app = self.app
        container = ttk.Frame(parent, style="Panel.TFrame")
        container.grid(row=0, column=0, sticky="nsew")
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)

        canvas = tk.Canvas(container, bg=app.colors["panel"], highlightthickness=0, borderwidth=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        content = ttk.Frame(canvas, style="Panel.TFrame")
        window_id = canvas.create_window((0, 0), window=content, anchor="nw")

        container.columnconfigure(0, weight=1)
        container.rowconfigure(0, weight=1)
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        canvas.configure(yscrollcommand=scrollbar.set)

        def update_scroll_region(_event: tk.Event) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))

        def resize_content(event: tk.Event) -> None:
            canvas.itemconfigure(window_id, width=event.width)

        def on_mousewheel(event: tk.Event) -> None:
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def bind_mousewheel(_event: tk.Event) -> None:
            canvas.bind_all("<MouseWheel>", on_mousewheel)

        def unbind_mousewheel(_event: tk.Event) -> None:
            canvas.unbind_all("<MouseWheel>")

        content.bind("<Configure>", update_scroll_region)
        canvas.bind("<Configure>", resize_content)
        canvas.bind("<Enter>", bind_mousewheel)
        canvas.bind("<Leave>", unbind_mousewheel)
        content.bind("<Enter>", bind_mousewheel)
        content.bind("<Leave>", unbind_mousewheel)
        return content

    def build(self) -> None:
        app = self.app
        app.columnconfigure(0, weight=0, minsize=212)
        app.columnconfigure(1, weight=1)
        app.rowconfigure(0, weight=1)

        sidebar = ttk.Frame(app, style="Sidebar.TFrame", padding=(14, 20))
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.columnconfigure(0, weight=1)
        sidebar.rowconfigure(7, weight=1)
        brand = ttk.Frame(sidebar, style="Sidebar.TFrame")
        brand.grid(row=0, column=0, sticky="ew", padx=(4, 0), pady=(0, 30))
        app.header_emblem_canvas = tk.Canvas(brand, width=48, height=42, bg=app.colors["panel_deep"], highlightthickness=0, borderwidth=0)
        app.header_emblem_canvas.grid(row=0, column=0, rowspan=2, sticky="w", padx=(0, 9))
        ttk.Label(brand, text="DAMIEN", style="Brand.TLabel").grid(row=0, column=1, sticky="sw")
        ttk.Label(brand, text="PERSONAL ASSISTANT", style="Eyebrow.TLabel").grid(row=1, column=1, sticky="nw", pady=(1, 0))

        app.status = tk.StringVar(value="Ready. Microphone capture is stopped until you press Hold to Talk.")
        app.mode_text = tk.StringVar(value="Desktop app")
        ttk.Label(sidebar, text="WORKSPACE", style="Eyebrow.TLabel").grid(row=1, column=0, sticky="w", padx=10, pady=(0, 9))

        main = ttk.Frame(app, style="TFrame", padding=(22, 20, 22, 18))
        main.grid(row=0, column=1, sticky="nsew")
        main.columnconfigure(0, weight=1)
        main.rowconfigure(2, weight=1)
        top = ttk.Frame(main, style="Topbar.TFrame", padding=(18, 13))
        top.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        top.columnconfigure(0, weight=1)
        app.page_title = tk.StringVar(value="Conversation")
        ttk.Label(top, textvariable=app.page_title, style="SectionTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(top, textvariable=app.status, style="PanelMuted.TLabel").grid(row=1, column=0, sticky="w", pady=(3, 0))
        indicator_row = tk.Frame(top, bg=app.colors["panel"])
        indicator_row.grid(row=0, column=1, rowspan=2, sticky="e", padx=(16, 0))
        app.listen_indicator = tk.Label(
            indicator_row,
            text="Mic muted",
            fg="#f4f7fa",
            bg=app.colors["danger"],
            padx=16,
            pady=7,
            font=("Segoe UI", 10, "bold"),
        )
        app.listen_indicator.grid(row=0, column=0, sticky="e", padx=(0, 8))
        app.mode_indicator = tk.Label(
            indicator_row,
            text="Local/free",
            fg="#f4f7fa",
            bg=app.colors["accent_dark"],
            padx=16,
            pady=7,
            font=("Segoe UI", 10, "bold"),
        )
        app.mode_indicator.grid(row=0, column=1, sticky="e")

        app.ollama_banner = tk.Frame(main, bg="#241b1d", padx=16, pady=12, highlightthickness=1, highlightbackground="#3d2f30")
        app.ollama_banner.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        app.ollama_banner.columnconfigure(0, weight=1)
        app.ollama_message = tk.StringVar(value="Checking local Ollama connection...")
        tk.Label(
            app.ollama_banner,
            textvariable=app.ollama_message,
            fg="#f7e6d0",
            bg="#2a2020",
            anchor="w",
            justify="left",
            font=("Segoe UI", 10),
        ).grid(row=0, column=0, sticky="ew")
        ttk.Button(app.ollama_banner, text="Start Ollama", command=app._start_ollama).grid(row=0, column=1, padx=(12, 0))
        ttk.Button(app.ollama_banner, text="Retry", command=app._check_ollama_async).grid(row=0, column=2, padx=(8, 0))
        ttk.Button(app.ollama_banner, text="Open Settings", command=app._open_settings_tab).grid(row=0, column=3, padx=(8, 0))

        app.notebook = ttk.Notebook(main, style="App.TNotebook")
        app.notebook.grid(row=2, column=0, sticky="nsew")

        chat_tab = ttk.Frame(app.notebook, style="Panel.TFrame", padding=14)
        settings_tab = ttk.Frame(app.notebook, style="Panel.TFrame", padding=14)
        memory_tab = ttk.Frame(app.notebook, style="Panel.TFrame", padding=14)
        benchmark_tab = ttk.Frame(app.notebook, style="Panel.TFrame", padding=14)
        app.notebook.add(chat_tab, text="Conversation")
        app.notebook.add(settings_tab, text="Settings")
        app.notebook.add(memory_tab, text="Memory")
        app.notebook.add(benchmark_tab, text="Benchmark")
        app.settings_tab = settings_tab

        app.nav_entries = []
        for row, (label, page, icon) in enumerate((
            ("Conversation", chat_tab, "◉"),
            ("Settings", settings_tab, "⚙"),
            ("Memory", memory_tab, "▤"),
            ("Benchmark", benchmark_tab, "⌁"),
        ), start=2):
            button = ttk.Button(
                sidebar,
                text=f"{icon}   {label}",
                style="Nav.TButton",
                command=lambda selected=page: app.notebook.select(selected),
            )
            button.grid(row=row, column=0, sticky="ew", pady=3)
            app.nav_entries.append((page, button, label))
        app.notebook.bind("<<NotebookTabChanged>>", lambda _event: self.sync_navigation())

        ttk.Separator(sidebar).grid(row=8, column=0, sticky="ew", pady=(12, 14))
        ttk.Label(sidebar, text="LOCAL SESSION", style="Eyebrow.TLabel").grid(row=9, column=0, sticky="w", padx=10)
        ttk.Label(sidebar, textvariable=app.mode_text, style="PanelMuted.TLabel").grid(row=10, column=0, sticky="w", padx=10, pady=(5, 2))
        ttk.Label(sidebar, text="Local desktop controls", style="PanelMuted.TLabel", wraplength=175).grid(
            row=11, column=0, sticky="w", padx=10, pady=(0, 6)
        )

        app._build_chat_tab(chat_tab)
        app._build_settings_tab(settings_tab)
        app._build_memory_tab(memory_tab)
        app._build_benchmark_tab(benchmark_tab)
        self.sync_navigation()
        app._animate_header_emblem()

    def sync_navigation(self) -> None:
        app = self.app
        if not hasattr(app, "nav_entries"):
            return
        current = app.notebook.select()
        for page, button, label in app.nav_entries:
            active = str(page) == current
            button.configure(style="NavActive.TButton" if active else "Nav.TButton")
            if active:
                app.page_title.set(label)

    def section(self, parent: ttk.Frame, title: str, row: int, column: int, **grid_options: Any) -> ttk.Frame:
        outer = ttk.Frame(parent, style="Panel.TFrame", padding=14)
        outer.grid(row=row, column=column, sticky="nsew", **grid_options)
        outer.columnconfigure(0, weight=1)
        ttk.Label(outer, text=title, style="SectionTitle.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 10))
        body = ttk.Frame(outer, style="Panel.TFrame")
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(1, weight=1)
        return body
