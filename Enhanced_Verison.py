"""
Pro Music Player  -  a feature-rich desktop player built with Tkinter + Pygame.

Install:   pip install pygame mutagen pillow
Optional:  pip install tkinterdnd2      (drag & drop files/folders onto the window)

Run:       python pro_music_player.py
"""

import io
import json
import math
import os
import random
import time
import tkinter as tk
from dataclasses import dataclass
from tkinter import colorchooser, filedialog, messagebox, simpledialog, ttk

import pygame
from mutagen import File as MutagenFile

try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    HAS_DND = True
except ImportError:
    HAS_DND = False

# ------------------------------------------------------------------ CONSTANTS
SUPPORTED = (".mp3", ".wav", ".ogg", ".flac")
CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".pro_music_player.json")
FONT = ("Segoe UI", 10)
COVER = 220
BARS = 28

THEMES = {
    "dark": dict(bg="#121212", panel="#1b1b1f", fg="#eaeaea",
                 muted="#9a9aa5", select="#2c2c36", field="#23232a"),
    "light": dict(bg="#f2f3f7", panel="#ffffff", fg="#1b1b1f",
                  muted="#666b78", select="#dfe6f7", field="#f7f8fb"),
}


# ------------------------------------------------------------------ DATA
@dataclass(eq=False)
class Track:
    id: int
    path: str
    title: str
    artist: str = "Unknown"
    album: str = "Unknown"
    duration: float = 0.0
    favorite: bool = False
    plays: int = 0


def fmt_time(sec):
    sec = max(0, int(sec))
    return f"{sec // 60}:{sec % 60:02d}"


def read_track(path, tid):
    """Build a Track from a file, reading tags with mutagen when possible."""
    title = os.path.splitext(os.path.basename(path))[0]
    artist = album = "Unknown"
    duration = 0.0
    try:
        audio = MutagenFile(path, easy=True)
        if audio is not None:
            if audio.info:
                duration = float(audio.info.length)
            title = (audio.get("title") or [title])[0]
            artist = (audio.get("artist") or [artist])[0]
            album = (audio.get("album") or [album])[0]
    except Exception:
        pass
    return Track(tid, path, title, artist, album, duration)


def get_cover(path):
    """Return embedded cover-art bytes (mp3 / flac) or None."""
    try:
        low = path.lower()
        if low.endswith(".mp3"):
            from mutagen.id3 import ID3
            pics = ID3(path).getall("APIC")
            return pics[0].data if pics else None
        if low.endswith(".flac"):
            from mutagen.flac import FLAC
            pics = FLAC(path).pictures
            return pics[0].data if pics else None
    except Exception:
        pass
    return None


# ------------------------------------------------------------------ APP
class MusicPlayer:
    def __init__(self, root):
        self.root = root
        root.title("Pro Music Player")
        root.geometry("1020x640")
        root.minsize(860, 540)

        try:
            pygame.mixer.init()
        except pygame.error as e:
            messagebox.showerror("Audio error", f"Could not start audio device:\n{e}")
            raise SystemExit

        # --- state
        self.tracks = []          # whole library (user order)
        self.by_id = {}
        self.visible = []         # tracks after search / filter
        self.queue = []           # "play next" queue
        self.history = []         # for smart "previous"
        self.current = None
        self.state = "stopped"    # stopped | playing | paused
        self.offset = 0.0         # seconds we started from (seeking)
        self.shuffle = False
        self.repeat = "off"       # off | all | one
        self.volume = 0.7
        self.muted = False
        self.theme = "dark"
        self.accent = "#1db954"
        self.sort_col, self.sort_rev = None, False
        self.next_id = 1
        self.dragging_seek = False
        self.drag_item = None
        self.drag_moved = False
        self.sleep_end = None
        self.levels = [0.0] * BARS
        self.cover_img = None

        self.style = ttk.Style()
        self.load_config()
        self.build_menu()
        self.build_ui()
        self.apply_theme()
        self.bind_keys()
        self.refresh_tree()
        self.apply_volume()
        self.update_mode_buttons()

        if HAS_DND:
            root.drop_target_register(DND_FILES)
            root.dnd_bind("<<Drop>>", lambda e: self.add_paths(root.tk.splitlist(e.data)))

        root.protocol("WM_DELETE_WINDOW", self.quit)
        self.tick()
        self.animate()
        self.set_status("Welcome! Add files (Ctrl+O) or a folder (Ctrl+Shift+O) to begin.")

    # -------------------------------------------------------------- CONFIG
    def load_config(self):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            return
        self.volume = cfg.get("volume", self.volume)
        self.shuffle = cfg.get("shuffle", False)
        self.repeat = cfg.get("repeat", "off")
        self.theme = cfg.get("theme", "dark")
        self.accent = cfg.get("accent", self.accent)
        if cfg.get("geometry"):
            self.root.geometry(cfg["geometry"])
        for item in cfg.get("tracks", []):
            if os.path.exists(item["path"]):
                t = read_track(item["path"], self.next_id)
                t.favorite = item.get("favorite", False)
                t.plays = item.get("plays", 0)
                self.add_track_obj(t)

    def save_config(self):
        cfg = dict(volume=self.volume, shuffle=self.shuffle, repeat=self.repeat,
                   theme=self.theme, accent=self.accent,
                   geometry=self.root.geometry(),
                   tracks=[dict(path=t.path, favorite=t.favorite, plays=t.plays)
                           for t in self.tracks])
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2)
        except OSError:
            pass

    # -------------------------------------------------------------- MENU
    def build_menu(self):
        m = tk.Menu(self.root)
        f = tk.Menu(m, tearoff=0)
        f.add_command(label="Add Files…", accelerator="Ctrl+O", command=self.add_files)
        f.add_command(label="Add Folder…", accelerator="Ctrl+Shift+O", command=self.add_folder)
        f.add_separator()
        f.add_command(label="Open Playlist (.m3u)…", command=self.load_playlist)
        f.add_command(label="Save Playlist (.m3u)…", command=self.save_playlist)
        f.add_separator()
        f.add_command(label="Clear Library", command=self.clear_library)
        f.add_command(label="Exit", accelerator="Ctrl+Q", command=self.quit)
        m.add_cascade(label="File", menu=f)

        p = tk.Menu(m, tearoff=0)
        p.add_command(label="Play / Pause", accelerator="Space", command=self.toggle_play)
        p.add_command(label="Next", accelerator="N", command=lambda: self.next_track())
        p.add_command(label="Previous", accelerator="P", command=self.prev_track)
        p.add_command(label="Stop", command=self.stop)
        p.add_separator()
        p.add_command(label="Toggle Shuffle", accelerator="S", command=self.toggle_shuffle)
        p.add_command(label="Cycle Repeat", accelerator="R", command=self.cycle_repeat)
        p.add_separator()
        sl = tk.Menu(p, tearoff=0)
        for mins in (15, 30, 45, 60):
            sl.add_command(label=f"{mins} minutes", command=lambda x=mins: self.set_sleep(x))
        sl.add_command(label="Custom…", command=self.custom_sleep)
        sl.add_separator()
        sl.add_command(label="Turn off", command=lambda: self.set_sleep(0))
        p.add_cascade(label="Sleep Timer", menu=sl)
        m.add_cascade(label="Playback", menu=p)

        v = tk.Menu(m, tearoff=0)
        v.add_command(label="Toggle Dark / Light Theme", command=self.toggle_theme)
        v.add_command(label="Accent Colour…", command=self.pick_accent)
        v.add_command(label="Always on Top", command=self.toggle_topmost)
        m.add_cascade(label="View", menu=v)

        h = tk.Menu(m, tearoff=0)
        h.add_command(label="Keyboard Shortcuts", command=self.show_shortcuts)
        m.add_cascade(label="Help", menu=h)
        self.root.config(menu=m)
        self.topmost = False

    # -------------------------------------------------------------- UI
    def build_ui(self):
        r = self.root
        r.columnconfigure(1, weight=1)
        r.rowconfigure(0, weight=1)

        # ---- left: now playing
        left = ttk.Frame(r, style="Panel.TFrame", padding=12)
        left.grid(row=0, column=0, sticky="ns")
        self.cover = tk.Canvas(left, width=COVER, height=COVER, highlightthickness=0)
        self.cover.pack()
        self.title_var = tk.StringVar(value="Nothing playing")
        self.artist_var = tk.StringVar(value="—")
        self.album_var = tk.StringVar(value="")
        ttk.Label(left, textvariable=self.title_var, style="Title.TLabel",
                  wraplength=COVER, justify="center").pack(pady=(12, 2))
        ttk.Label(left, textvariable=self.artist_var, style="Panel.TLabel").pack()
        ttk.Label(left, textvariable=self.album_var, style="Muted.TLabel").pack(pady=(0, 10))
        self.viz = tk.Canvas(left, width=COVER, height=70, highlightthickness=0)
        self.viz.pack(pady=4)
        self.stats_var = tk.StringVar()
        ttk.Label(left, textvariable=self.stats_var, style="Muted.TLabel").pack(side="bottom", pady=(8, 0))

        # ---- right: library
        right = ttk.Frame(r, padding=(12, 12, 12, 0))
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)

        top = ttk.Frame(right)
        top.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        top.columnconfigure(1, weight=1)
        ttk.Label(top, text="🔍").grid(row=0, column=0, padx=(0, 4))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *a: self.refresh_tree())
        self.search_entry = ttk.Entry(top, textvariable=self.search_var)
        self.search_entry.grid(row=0, column=1, sticky="ew")
        self.filter_var = tk.StringVar(value="All")
        cb = ttk.Combobox(top, textvariable=self.filter_var, width=12, state="readonly",
                          values=["All", "Favorites", "Most played"])
        cb.grid(row=0, column=2, padx=6)
        cb.bind("<<ComboboxSelected>>", lambda e: self.refresh_tree())
        ttk.Button(top, text="＋ Files", command=self.add_files).grid(row=0, column=3)
        ttk.Button(top, text="＋ Folder", command=self.add_folder).grid(row=0, column=4, padx=(6, 0))

        self.nb = ttk.Notebook(right)
        self.nb.grid(row=1, column=0, sticky="nsew")

        # library tab
        lib = ttk.Frame(self.nb)
        lib.columnconfigure(0, weight=1)
        lib.rowconfigure(0, weight=1)
        cols = ("fav", "title", "artist", "album", "dur", "plays")
        self.tree = ttk.Treeview(lib, columns=cols, show="headings", selectmode="extended")
        self.col_names = dict(fav="♥", title="Title", artist="Artist",
                              album="Album", dur="Time", plays="Plays")
        widths = dict(fav=36, title=240, artist=140, album=140, dur=60, plays=50)
        for c in cols:
            self.tree.heading(c, text=self.col_names[c], command=lambda c=c: self.sort_by(c))
            self.tree.column(c, width=widths[c], anchor="center" if c in ("fav", "dur", "plays") else "w",
                             stretch=c in ("title", "artist", "album"))
        sb = ttk.Scrollbar(lib, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        sb.grid(row=0, column=1, sticky="ns")
        self.nb.add(lib, text="  Library  ")

        # queue tab
        qf = ttk.Frame(self.nb)
        qf.columnconfigure(0, weight=1)
        qf.rowconfigure(0, weight=1)
        self.qlist = tk.Listbox(qf, highlightthickness=0, borderwidth=0, font=FONT, activestyle="none")
        self.qlist.grid(row=0, column=0, sticky="nsew")
        qb = ttk.Frame(qf)
        qb.grid(row=1, column=0, sticky="ew", pady=6)
        ttk.Button(qb, text="Remove", command=self.queue_remove).pack(side="left", padx=4)
        ttk.Button(qb, text="Clear queue", command=self.queue_clear).pack(side="left")
        self.qlist.bind("<Double-1>", self.queue_play)
        self.nb.add(qf, text="  Queue  ")

        # tree bindings
        self.tree.bind("<Double-1>", lambda e: self.play_selected())
        self.tree.bind("<Return>", lambda e: self.play_selected())
        self.tree.bind("<space>", lambda e: (self.toggle_play(), "break")[1])
        self.tree.bind("<Delete>", lambda e: self.remove_selected())
        self.tree.bind("<ButtonPress-1>", self.tree_press)
        self.tree.bind("<B1-Motion>", self.tree_motion)
        self.tree.bind("<ButtonRelease-1>", self.tree_release)
        self.tree.bind("<Button-3>", self.show_context)
        self.tree.bind("<Button-2>", self.show_context)

        self.ctx = tk.Menu(self.root, tearoff=0)
        self.ctx.add_command(label="▶  Play", command=self.play_selected)
        self.ctx.add_command(label="⏭  Play next", command=lambda: self.enqueue(front=True))
        self.ctx.add_command(label="➕  Add to queue", command=self.enqueue)
        self.ctx.add_separator()
        self.ctx.add_command(label="♥  Toggle favourite", command=self.toggle_fav_selected)
        self.ctx.add_command(label="▲  Move up", command=lambda: self.move_selected(-1))
        self.ctx.add_command(label="▼  Move down", command=lambda: self.move_selected(1))
        self.ctx.add_separator()
        self.ctx.add_command(label="ℹ  Track info", command=self.show_info)
        self.ctx.add_command(label="✖  Remove from library", command=self.remove_selected)

        # ---- bottom: transport
        bottom = ttk.Frame(r, style="Panel.TFrame", padding=(14, 8))
        bottom.grid(row=1, column=0, columnspan=2, sticky="ew")
        bottom.columnconfigure(1, weight=1)

        self.time_var = tk.StringVar(value="0:00")
        self.total_var = tk.StringVar(value="0:00")
        ttk.Label(bottom, textvariable=self.time_var, style="Panel.TLabel", width=6).grid(row=0, column=0)
        self.seek = ttk.Scale(bottom, from_=0, to=1000, orient="horizontal")
        self.seek.grid(row=0, column=1, sticky="ew", padx=6)
        ttk.Label(bottom, textvariable=self.total_var, style="Panel.TLabel", width=6).grid(row=0, column=2)
        self.seek.bind("<ButtonPress-1>", self.seek_press)
        self.seek.bind("<B1-Motion>", self.seek_drag)
        self.seek.bind("<ButtonRelease-1>", self.seek_release)

        ctl = ttk.Frame(bottom, style="Panel.TFrame")
        ctl.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(6, 0))
        ctl.columnconfigure(1, weight=1)
        ctl.columnconfigure(3, weight=1)

        modes = ttk.Frame(ctl, style="Panel.TFrame")
        modes.grid(row=0, column=0, sticky="w")
        self.shuffle_btn = ttk.Button(modes, text="🔀 Shuffle", command=self.toggle_shuffle)
        self.shuffle_btn.pack(side="left", padx=(0, 6))
        self.repeat_btn = ttk.Button(modes, text="🔁 Off", command=self.cycle_repeat, width=9)
        self.repeat_btn.pack(side="left")

        mid = ttk.Frame(ctl, style="Panel.TFrame")
        mid.grid(row=0, column=2)
        ttk.Button(mid, text="⏮", width=4, command=self.prev_track).pack(side="left", padx=3)
        ttk.Button(mid, text="⏪ 10", width=6, command=lambda: self.seek_rel(-10)).pack(side="left", padx=3)
        self.play_text = tk.StringVar(value="▶")
        ttk.Button(mid, textvariable=self.play_text, style="Play.TButton", width=4,
                   command=self.toggle_play).pack(side="left", padx=6)
        ttk.Button(mid, text="10 ⏩", width=6, command=lambda: self.seek_rel(10)).pack(side="left", padx=3)
        ttk.Button(mid, text="⏭", width=4, command=lambda: self.next_track()).pack(side="left", padx=3)
        ttk.Button(mid, text="⏹", width=4, command=self.stop).pack(side="left", padx=3)

        vol = ttk.Frame(ctl, style="Panel.TFrame")
        vol.grid(row=0, column=4, sticky="e")
        self.mute_btn = ttk.Button(vol, text="🔊", width=4, command=self.toggle_mute)
        self.mute_btn.pack(side="left")
        self.vol_scale = ttk.Scale(vol, from_=0, to=100, orient="horizontal", length=120,
                                   command=self.on_volume)
        self.vol_scale.set(self.volume * 100)
        self.vol_scale.pack(side="left", padx=6)
        self.vol_label = ttk.Label(vol, text="70%", style="Panel.TLabel", width=5)
        self.vol_label.pack(side="left")

        # ---- status bar
        sbar = ttk.Frame(r, style="Panel.TFrame")
        sbar.grid(row=2, column=0, columnspan=2, sticky="ew")
        sbar.columnconfigure(0, weight=1)
        self.status_var = tk.StringVar()
        self.sleep_var = tk.StringVar()
        ttk.Label(sbar, textvariable=self.status_var, style="Status.TLabel", anchor="w").grid(
            row=0, column=0, sticky="ew", padx=10, pady=3)
        ttk.Label(sbar, textvariable=self.sleep_var, style="Status.TLabel").grid(row=0, column=1, padx=10)

    # -------------------------------------------------------------- THEME
    def apply_theme(self):
        t, a, s = THEMES[self.theme], self.accent, self.style
        s.theme_use("clam")
        self.root.config(bg=t["bg"])
        s.configure(".", background=t["bg"], foreground=t["fg"],
                    fieldbackground=t["field"], font=FONT, bordercolor=t["bg"])
        s.configure("TFrame", background=t["bg"])
        s.configure("Panel.TFrame", background=t["panel"])
        s.configure("TLabel", background=t["bg"], foreground=t["fg"])
        s.configure("Panel.TLabel", background=t["panel"], foreground=t["fg"])
        s.configure("Title.TLabel", background=t["panel"], foreground=t["fg"],
                    font=(FONT[0], 14, "bold"))
        s.configure("Muted.TLabel", background=t["panel"], foreground=t["muted"])
        s.configure("Status.TLabel", background=t["panel"], foreground=t["muted"])
        s.configure("TButton", background=t["field"], foreground=t["fg"],
                    borderwidth=0, padding=(10, 6), focuscolor=t["field"])
        s.map("TButton", background=[("active", t["select"])])
        for name, size in (("On.TButton", 10), ("Play.TButton", 14)):
            s.configure(name, background=a, foreground="#ffffff",
                        font=(FONT[0], size, "bold"), focuscolor=a)
            s.map(name, background=[("active", a)])
        s.configure("Play.TButton", padding=(16, 8))
        s.configure("Treeview", background=t["field"], fieldbackground=t["field"],
                    foreground=t["fg"], rowheight=28, borderwidth=0)
        s.map("Treeview", background=[("selected", t["select"])],
              foreground=[("selected", t["fg"])])
        s.configure("Treeview.Heading", background=t["panel"], foreground=t["muted"],
                    relief="flat", font=(FONT[0], 10, "bold"))
        s.map("Treeview.Heading", background=[("active", t["select"])])
        s.configure("TEntry", fieldbackground=t["field"], foreground=t["fg"], insertcolor=t["fg"])
        s.configure("TCombobox", fieldbackground=t["field"], background=t["field"],
                    foreground=t["fg"], arrowcolor=t["fg"])
        s.map("TCombobox", fieldbackground=[("readonly", t["field"])],
              foreground=[("readonly", t["fg"])])
        s.configure("TNotebook", background=t["bg"], borderwidth=0)
        s.configure("TNotebook.Tab", background=t["panel"], foreground=t["muted"], padding=(14, 6))
        s.map("TNotebook.Tab", background=[("selected", t["field"])],
              foreground=[("selected", a)])
        s.configure("Horizontal.TScale", background=a, troughcolor=t["select"])
        s.configure("Vertical.TScrollbar", background=t["panel"], troughcolor=t["field"],
                    arrowcolor=t["muted"])

        self.cover.config(bg=t["field"])
        self.viz.config(bg=t["panel"])
        self.qlist.config(bg=t["field"], fg=t["fg"], selectbackground=t["select"],
                          selectforeground=a)
        self.tree.tag_configure("playing", foreground=a)
        self.ctx.config(bg=t["panel"], fg=t["fg"], activebackground=a)
        self.draw_cover(get_cover(self.current.path) if self.current else None)

    def toggle_theme(self):
        self.theme = "light" if self.theme == "dark" else "dark"
        self.apply_theme()

    def pick_accent(self):
        c = colorchooser.askcolor(color=self.accent, title="Choose accent colour")[1]
        if c:
            self.accent = c
            self.apply_theme()
            self.update_mode_buttons()

    def toggle_topmost(self):
        self.topmost = not self.topmost
        self.root.attributes("-topmost", self.topmost)

    # -------------------------------------------------------------- LIBRARY
    def add_track_obj(self, t):
        self.tracks.append(t)
        self.by_id[t.id] = t
        self.next_id = max(self.next_id, t.id) + 1

    def add_files(self):
        paths = filedialog.askopenfilenames(
            title="Select songs",
            filetypes=[("Audio", "*.mp3 *.wav *.ogg *.flac"), ("All files", "*.*")])
        self.add_paths(paths)

    def add_folder(self):
        folder = filedialog.askdirectory(title="Select a music folder")
        if folder:
            self.add_paths([folder])

    def add_paths(self, paths):
        existing = {t.path for t in self.tracks}
        files = []
        for p in paths:
            if os.path.isdir(p):
                for dp, _, fns in os.walk(p):
                    files += [os.path.join(dp, f) for f in sorted(fns)
                              if f.lower().endswith(SUPPORTED)]
            elif p.lower().endswith(SUPPORTED):
                files.append(p)
        added = 0
        for p in files:
            p = os.path.normpath(p)
            if p in existing:
                continue
            self.add_track_obj(read_track(p, self.next_id))
            existing.add(p)
            added += 1
            if added % 20 == 0:
                self.set_status(f"Reading tags… {added}/{len(files)}")
                self.root.update_idletasks()
        self.refresh_tree()
        self.set_status(f"Added {added} track(s)." if added else "No new supported audio files found.")

    def clear_library(self):
        if self.tracks and messagebox.askyesno("Clear library", "Remove all tracks from the library?"):
            self.stop()
            self.tracks.clear()
            self.by_id.clear()
            self.queue.clear()
            self.history.clear()
            self.current = None
            self.refresh_tree()
            self.refresh_queue()

    def save_playlist(self):
        if not self.tracks:
            return
        path = filedialog.asksaveasfilename(defaultextension=".m3u",
                                            filetypes=[("M3U playlist", "*.m3u")])
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write("#EXTM3U\n")
                for t in self.tracks:
                    f.write(f"#EXTINF:{int(t.duration)},{t.artist} - {t.title}\n{t.path}\n")
            self.set_status(f"Saved playlist: {os.path.basename(path)}")

    def load_playlist(self):
        path = filedialog.askopenfilename(filetypes=[("M3U playlist", "*.m3u *.m3u8")])
        if path:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                self.add_paths([ln.strip() for ln in f if ln.strip() and not ln.startswith("#")])

    # ---- filtering / sorting / tree
    def is_filtered(self):
        return bool(self.search_var.get().strip()) or self.filter_var.get() != "All"

    def filtered(self):
        q = self.search_var.get().strip().lower()
        mode = self.filter_var.get()
        out = []
        for t in self.tracks:
            if q and q not in f"{t.title} {t.artist} {t.album}".lower():
                continue
            if mode == "Favorites" and not t.favorite:
                continue
            if mode == "Most played" and t.plays == 0:
                continue
            out.append(t)
        if mode == "Most played":
            out = sorted(out, key=lambda t: -t.plays)[:25]
        return out

    def row_values(self, t):
        return ("♥" if t.favorite else "♡", t.title, t.artist, t.album,
                fmt_time(t.duration), t.plays)

    def refresh_tree(self):
        selected = set(self.tree.selection())
        self.tree.delete(*self.tree.get_children())
        self.visible = self.filtered()
        for t in self.visible:
            tags = ("playing",) if t is self.current else ()
            self.tree.insert("", "end", iid=str(t.id), values=self.row_values(t), tags=tags)
        keep = [i for i in selected if self.tree.exists(i)]
        if keep:
            self.tree.selection_set(keep)
        total = sum(t.duration for t in self.tracks)
        h, m = divmod(int(total) // 60, 60)
        self.stats_var.set(f"{len(self.visible)} of {len(self.tracks)} tracks • {h}h {m:02d}m")

    def sort_by(self, col):
        keys = dict(fav=lambda t: t.favorite, title=lambda t: t.title.lower(),
                    artist=lambda t: t.artist.lower(), album=lambda t: t.album.lower(),
                    dur=lambda t: t.duration, plays=lambda t: t.plays)
        self.sort_rev = (not self.sort_rev) if self.sort_col == col else False
        self.sort_col = col
        self.tracks.sort(key=keys[col], reverse=self.sort_rev)
        for c, name in self.col_names.items():
            arrow = (" ▼" if self.sort_rev else " ▲") if c == col else ""
            self.tree.heading(c, text=name + arrow)
        self.refresh_tree()

    def selected_tracks(self):
        return [self.by_id[int(i)] for i in self.tree.selection() if int(i) in self.by_id]

    # ---- mouse: click-heart, drag-reorder, context menu
    def tree_press(self, e):
        row = self.tree.identify_row(e.y)
        self.drag_item, self.drag_moved = None, False
        if not row:
            return
        if self.tree.identify_column(e.x) == "#1":       # clicked the heart
            t = self.by_id[int(row)]
            t.favorite = not t.favorite
            self.tree.item(row, values=self.row_values(t))
            if self.filter_var.get() == "Favorites":
                self.refresh_tree()
            return "break"
        self.drag_item = row

    def tree_motion(self, e):
        if not self.drag_item or self.is_filtered():
            return
        target = self.tree.identify_row(e.y)
        if target and target != self.drag_item:
            self.tree.move(self.drag_item, "", self.tree.index(target))
            self.drag_moved = True

    def tree_release(self, e):
        if self.drag_moved:
            self.tracks = [self.by_id[int(i)] for i in self.tree.get_children()]
            self.visible = list(self.tracks)
            self.sort_col = None
            self.set_status("Playlist order changed.")
        self.drag_item, self.drag_moved = None, False

    def show_context(self, e):
        row = self.tree.identify_row(e.y)
        if row:
            if row not in self.tree.selection():
                self.tree.selection_set(row)
            self.ctx.tk_popup(e.x_root, e.y_root)

    def move_selected(self, delta):
        if self.is_filtered():
            self.set_status("Clear search / filter to reorder tracks.")
            return
        sel = self.selected_tracks()
        idx = sorted(self.tracks.index(t) for t in sel)
        if not idx or idx[0] + delta < 0 or idx[-1] + delta >= len(self.tracks):
            return
        for i in (idx if delta < 0 else reversed(idx)):
            self.tracks[i], self.tracks[i + delta] = self.tracks[i + delta], self.tracks[i]
        self.refresh_tree()

    def toggle_fav_selected(self):
        for t in self.selected_tracks():
            t.favorite = not t.favorite
        self.refresh_tree()

    def remove_selected(self):
        sel = self.selected_tracks()
        if not sel:
            return
        for t in sel:
            if t is self.current:
                self.stop()
                self.current = None
                self.show_now_playing(None)
            self.tracks.remove(t)
            del self.by_id[t.id]
            self.queue = [q for q in self.queue if q is not t]
            self.history = [h for h in self.history if h is not t]
        self.refresh_tree()
        self.refresh_queue()
        self.set_status(f"Removed {len(sel)} track(s).")

    def show_info(self):
        sel = self.selected_tracks()
        if not sel:
            return
        t = sel[0]
        size = os.path.getsize(t.path) / (1024 * 1024) if os.path.exists(t.path) else 0
        messagebox.showinfo("Track info",
                            f"Title:    {t.title}\nArtist:   {t.artist}\nAlbum:    {t.album}\n"
                            f"Length:   {fmt_time(t.duration)}\nPlays:    {t.plays}\n"
                            f"Size:     {size:.1f} MB\n\nPath:\n{t.path}")

    # -------------------------------------------------------------- QUEUE
    def enqueue(self, front=False):
        sel = self.selected_tracks()
        if front:
            self.queue = sel + self.queue
        else:
            self.queue += sel
        self.refresh_queue()
        self.set_status(f"Queued {len(sel)} track(s).")

    def refresh_queue(self):
        self.qlist.delete(0, tk.END)
        for i, t in enumerate(self.queue, 1):
            self.qlist.insert(tk.END, f"  {i}.  {t.title}  —  {t.artist}")
        self.nb.tab(1, text=f"  Queue ({len(self.queue)})  " if self.queue else "  Queue  ")

    def queue_remove(self):
        for i in reversed(self.qlist.curselection()):
            del self.queue[i]
        self.refresh_queue()

    def queue_clear(self):
        self.queue.clear()
        self.refresh_queue()

    def queue_play(self, e):
        sel = self.qlist.curselection()
        if sel:
            t = self.queue.pop(sel[0])
            self.refresh_queue()
            self.play_track(t)

    # -------------------------------------------------------------- PLAYBACK
    def _start(self, path, start):
        """Load + play; returns the real start offset (falls back to 0 if unsupported)."""
        pygame.mixer.music.load(path)
        try:
            pygame.mixer.music.play(start=start)
            return start
        except pygame.error:
            pygame.mixer.music.play()
            return 0.0

    def play_track(self, track):
        if not os.path.exists(track.path):
            messagebox.showwarning("File missing", f"Cannot find:\n{track.path}")
            return False
        try:
            self.offset = self._start(track.path, 0.0)
        except pygame.error as e:
            messagebox.showerror("Playback error", str(e))
            return False
        self.current = track
        self.state = "playing"
        track.plays += 1
        self.history.append(track)
        self.history = self.history[-200:]
        self.play_text.set("⏸")
        self.show_now_playing(track)
        self.set_status(f"Playing: {track.title}")
        return True

    def show_now_playing(self, t):
        if t:
            self.title_var.set(t.title)
            self.artist_var.set(t.artist)
            self.album_var.set(t.album)
            self.total_var.set(fmt_time(t.duration))
            self.root.title(f"♪ {t.title} — Pro Music Player")
            self.draw_cover(get_cover(t.path))
        else:
            self.title_var.set("Nothing playing")
            self.artist_var.set("—")
            self.album_var.set("")
            self.total_var.set("0:00")
            self.time_var.set("0:00")
            self.seek.set(0)
            self.root.title("Pro Music Player")
            self.draw_cover(None)
        for iid in self.tree.get_children():
            tr = self.by_id[int(iid)]
            self.tree.item(iid, values=self.row_values(tr),
                           tags=("playing",) if tr is t else ())
        if t and self.tree.exists(str(t.id)):
            self.tree.see(str(t.id))

    def draw_cover(self, data):
        self.cover.delete("all")
        self.cover_img = None
        if data and HAS_PIL:
            try:
                img = Image.open(io.BytesIO(data)).convert("RGB").resize((COVER, COVER))
                self.cover_img = ImageTk.PhotoImage(img)
                self.cover.create_image(0, 0, anchor="nw", image=self.cover_img)
                return
            except Exception:
                pass
        self.cover.create_text(COVER // 2, COVER // 2, text="♪",
                               font=("Segoe UI", 80), fill=self.accent)

    def play_selected(self):
        sel = self.selected_tracks()
        if sel:
            self.play_track(sel[0])

    def toggle_play(self):
        if self.state == "playing":
            pygame.mixer.music.pause()
            self.state = "paused"
            self.play_text.set("▶")
            self.set_status("Paused")
        elif self.state == "paused":
            pygame.mixer.music.unpause()
            self.state = "playing"
            self.play_text.set("⏸")
            self.set_status(f"Playing: {self.current.title}")
        else:
            sel = self.selected_tracks()
            lst = self.visible or self.tracks
            if sel:
                self.play_track(sel[0])
            elif lst:
                self.play_track(random.choice(lst) if self.shuffle else lst[0])
            else:
                self.set_status("Library is empty — add some music first.")

    def stop(self):
        pygame.mixer.music.stop()
        self.state = "stopped"
        self.offset = 0.0
        self.play_text.set("▶")
        self.time_var.set("0:00")
        self.seek.set(0)
        self.set_status("Stopped")

    def next_track(self, auto=False):
        if self.queue:
            t = self.queue.pop(0)
            self.refresh_queue()
            return self.play_track(t)
        lst = self.visible or self.tracks
        if not lst:
            return False
        if auto and self.repeat == "one" and self.current:
            return self.play_track(self.current)
        if self.shuffle:
            pool = [t for t in lst if t is not self.current] or lst
            return self.play_track(random.choice(pool))
        i = lst.index(self.current) + 1 if self.current in lst else 0
        if i >= len(lst):
            if auto and self.repeat == "off":
                return False
            i = 0
        return self.play_track(lst[i])

    def prev_track(self):
        if self.state != "stopped" and self.position() > 3:
            self.seek_to(0)
            return
        while len(self.history) > 1:
            self.history.pop()
            t = self.history.pop()
            if t.id in self.by_id:
                self.play_track(t)
                return
        lst = self.visible or self.tracks
        if lst:
            i = (lst.index(self.current) - 1) % len(lst) if self.current in lst else 0
            self.play_track(lst[i])

    def on_track_end(self):
        if not self.next_track(auto=True):
            self.stop()
            self.set_status("Reached the end of the playlist.")

    # ---- seeking
    def position(self):
        if self.state == "stopped" or not self.current:
            return 0.0
        pos = self.offset + max(0, pygame.mixer.music.get_pos()) / 1000
        d = self.current.duration
        return min(pos, d) if d else pos

    def seek_to(self, pos):
        if not self.current or self.state == "stopped":
            return
        pos = max(0.0, min(pos, max(self.current.duration - 0.5, 0)))
        was_paused = self.state == "paused"
        try:
            self.offset = self._start(self.current.path, pos)
        except pygame.error:
            return
        if was_paused:
            pygame.mixer.music.pause()

    def seek_rel(self, delta):
        if self.state != "stopped":
            self.seek_to(self.position() + delta)

    def _frac(self, e):
        return min(max(e.x / max(self.seek.winfo_width(), 1), 0.0), 1.0)

    def seek_press(self, e):
        self.dragging_seek = True
        self.seek_drag(e)
        return "break"

    def seek_drag(self, e):
        if self.current:
            f = self._frac(e)
            self.seek.set(f * 1000)
            self.time_var.set(fmt_time(f * self.current.duration))
        return "break"

    def seek_release(self, e):
        self.dragging_seek = False
        if self.current:
            self.seek_to(self._frac(e) * self.current.duration)
        return "break"

    # ---- modes / volume
    def toggle_shuffle(self):
        self.shuffle = not self.shuffle
        self.update_mode_buttons()
        self.set_status(f"Shuffle {'on' if self.shuffle else 'off'}")

    def cycle_repeat(self):
        self.repeat = {"off": "all", "all": "one", "one": "off"}[self.repeat]
        self.update_mode_buttons()
        self.set_status(f"Repeat: {self.repeat}")

    def update_mode_buttons(self):
        self.shuffle_btn.config(style="On.TButton" if self.shuffle else "TButton")
        icon = "🔂" if self.repeat == "one" else "🔁"
        self.repeat_btn.config(text=f"{icon} {self.repeat.title()}",
                               style="On.TButton" if self.repeat != "off" else "TButton")

    def on_volume(self, val):
        self.volume = float(val) / 100
        if self.muted and self.volume > 0:
            self.muted = False
        self.apply_volume()

    def apply_volume(self):
        pygame.mixer.music.set_volume(0 if self.muted else self.volume)
        shown = 0 if self.muted else int(self.volume * 100)
        self.vol_label.config(text=f"{shown}%")
        self.mute_btn.config(text="🔇" if self.muted or shown == 0 else "🔊")

    def nudge_volume(self, delta):
        v = min(100, max(0, self.volume * 100 + delta))
        self.vol_scale.set(v)

    def toggle_mute(self):
        self.muted = not self.muted
        self.apply_volume()

    # ---- sleep timer
    def set_sleep(self, minutes):
        if minutes <= 0:
            self.sleep_end = None
            self.sleep_var.set("")
            self.set_status("Sleep timer off")
        else:
            self.sleep_end = time.time() + minutes * 60
            self.set_status(f"Sleep timer set for {minutes} minute(s)")

    def custom_sleep(self):
        m = simpledialog.askinteger("Sleep timer", "Stop playback after how many minutes?",
                                    minvalue=1, maxvalue=600, parent=self.root)
        if m:
            self.set_sleep(m)

    # -------------------------------------------------------------- LOOPS
    def tick(self):
        if self.state == "playing" and not pygame.mixer.music.get_busy():
            self.on_track_end()
        if self.current and self.state != "stopped":
            pos = self.position()
            if not self.dragging_seek:
                self.time_var.set(fmt_time(pos))
                d = self.current.duration
                self.seek.set(pos / d * 1000 if d else 0)
        if self.sleep_end:
            left = self.sleep_end - time.time()
            if left <= 0:
                self.sleep_end = None
                self.sleep_var.set("")
                pygame.mixer.music.fadeout(2500)
                self.root.after(2600, self.stop)
                self.set_status("Sleep timer finished — goodnight 😴")
            else:
                self.sleep_var.set(f"😴 {fmt_time(left)}")
        self.root.after(250, self.tick)

    def animate(self):
        """Animated equaliser bars. NOTE: simulated — pygame can't expose real audio spectrum."""
        w, h = COVER, 70
        gap = 3
        bw = (w - gap * (BARS - 1)) / BARS
        now = time.time()
        playing = self.state == "playing"
        for i in range(BARS):
            if playing:
                target = (0.2 + 0.8 * abs(math.sin(now * 3 + i * 0.55))) * random.uniform(0.45, 1)
                self.levels[i] = self.levels[i] * 0.55 + target * 0.45
            else:
                self.levels[i] *= 0.85
        self.viz.delete("all")
        for i, lv in enumerate(self.levels):
            x = i * (bw + gap)
            self.viz.create_rectangle(x, h - lv * h, x + bw, h, fill=self.accent, outline="")
        self.root.after(50, self.animate)

    # -------------------------------------------------------------- MISC
    def bind_keys(self):
        def guard(fn):
            def handler(e):
                if isinstance(self.root.focus_get(), (tk.Entry, ttk.Entry, ttk.Combobox)):
                    return
                fn()
                return "break"
            return handler

        for key, fn in {
            "<space>": self.toggle_play,
            "<Left>": lambda: self.seek_rel(-5),
            "<Right>": lambda: self.seek_rel(5),
            "n": self.next_track, "p": self.prev_track, "m": self.toggle_mute,
            "s": self.toggle_shuffle, "r": self.cycle_repeat,
            "f": self.toggle_fav_current,
        }.items():
            self.root.bind(key, guard(fn))
        self.root.bind("<Control-Up>", lambda e: self.nudge_volume(5))
        self.root.bind("<Control-Down>", lambda e: self.nudge_volume(-5))
        self.root.bind("<Control-o>", lambda e: self.add_files())
        self.root.bind("<Control-O>", lambda e: self.add_folder())
        self.root.bind("<Control-f>", lambda e: self.search_entry.focus_set())
        self.root.bind("<Control-q>", lambda e: self.quit())
        self.root.bind("<Escape>", lambda e: (self.search_var.set(""), self.root.focus_set()))

    def toggle_fav_current(self):
        if self.current:
            self.current.favorite = not self.current.favorite
            self.refresh_tree()
            self.set_status(("♥ Added to" if self.current.favorite else "Removed from") + " favourites")

    def show_shortcuts(self):
        messagebox.showinfo("Keyboard shortcuts",
                            "Space\t\tPlay / Pause\nN / P\t\tNext / Previous\n"
                            "← / →\t\tSeek -5s / +5s\nCtrl+↑ / ↓\tVolume\n"
                            "M\t\tMute\nS\t\tShuffle\nR\t\tCycle repeat\nF\t\tFavourite current song\n"
                            "Ctrl+O\t\tAdd files\nCtrl+Shift+O\tAdd folder\n"
                            "Ctrl+F\t\tSearch\nEsc\t\tClear search\nDel\t\tRemove selected\n\n"
                            "Mouse: double-click to play, right-click for menu,\n"
                            "click ♥ to favourite, drag rows to reorder,\n"
                            "click column headers to sort, drag the seek bar.")

    def set_status(self, text):
        self.status_var.set(text)

    def quit(self):
        self.save_config()
        pygame.mixer.quit()
        self.root.destroy()


if __name__ == "__main__":
    root = TkinterDnD.Tk() if HAS_DND else tk.Tk()
    MusicPlayer(root)
    root.mainloop()
