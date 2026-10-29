# 🎧 Pro Music Player

A feature-rich desktop music player written in Python with **Tkinter** and **Pygame**. It has a library view, a play queue, seekable playback, album art, themes and a lot of keyboard and mouse shortcuts, and it remembers your session between launches.

<!-- Add a screenshot: save it as screenshot.png in the repo and uncomment the line below -->
<!-- ![Pro Music Player screenshot](screenshot.png) -->

## ✨ Features

**Playback**
- Play, pause, stop, next and previous, with a seekable progress bar (click or drag) and ±10 s skip buttons
- Shuffle, plus repeat modes: **Off / All / One**
- Smart "previous": restarts the song if more than 3 s in, otherwise returns to the last song played
- Volume slider and mute
- Sleep timer (15 / 30 / 45 / 60 min or custom) with a fade-out

**Library and playlists**
- Add individual files or whole folders (scanned recursively)
- Reads title, artist, album and duration from tags (via `mutagen`)
- Sortable columns: click any header
- Live search across title, artist and album
- Filters: **All**, **Favourites** and **Most played** (top 25)
- Favourites: click the ♥ in a row or press `F`
- Play counts are tracked per song
- Drag rows to reorder, or use Move up / Move down
- Open and save `.m3u` playlists
- Track info dialog (length, size, path and more)

**Play queue**
- "Play next" and "Add to queue" from the right-click menu
- A dedicated Queue tab, where you can double-click to play or remove items

**Interface**
- Album art display (mp3 and flac embedded covers; needs Pillow)
- Animated equaliser bars (visual only, see [Limitations](#-limitations))
- Dark and light themes, with a custom accent colour picker
- Always-on-top option
- Optional drag-and-drop of files and folders onto the window
- Session restore: library, favourites, play counts, volume, shuffle, repeat, theme and window size

## 📦 Supported formats

`.mp3` · `.wav` · `.ogg` · `.flac`

## 🚀 Installation

**Requirements:** Python 3.8 or newer.

```bash
git clone https://github.com/<your-username>/pro-music-player.git
cd pro-music-player
pip install -r requirements.txt
python pro_music_player.py
```

Or install the dependencies manually:

```bash
pip install pygame mutagen pillow
pip install tkinterdnd2   # optional: drag & drop support
```

> **Linux:** Tkinter is not always bundled with Python. Install it with  
> `sudo apt install python3-tk` (Debian/Ubuntu) or `sudo dnf install python3-tkinter` (Fedora).

## 🎮 Usage

1. Click **＋ Files** or **＋ Folder** (or press `Ctrl+O` / `Ctrl+Shift+O`), or drag music onto the window.
2. Double-click a song to play it.
3. Right-click a song for queue, favourite, reorder, info and remove options.

### Keyboard shortcuts

| Key | Action |
|---|---|
| `Space` | Play / Pause |
| `N` / `P` | Next / Previous |
| `←` / `→` | Seek −5 s / +5 s |
| `Ctrl` + `↑` / `↓` | Volume up / down |
| `M` | Mute |
| `S` | Toggle shuffle |
| `R` | Cycle repeat mode |
| `F` | Favourite the current song |
| `Ctrl+O` | Add files |
| `Ctrl+Shift+O` | Add folder |
| `Ctrl+F` | Focus search |
| `Esc` | Clear search |
| `Del` | Remove selected tracks from the library |
| `Ctrl+Q` | Quit |

Single-letter shortcuts are ignored while you are typing in the search box.

### Mouse

| Action | Result |
|---|---|
| Double-click a row | Play it |
| Right-click a row | Context menu |
| Click the ♥ column | Toggle favourite |
| Drag a row | Reorder (only when no search or filter is active) |
| Click a column header | Sort (click again to reverse) |
| Click or drag the seek bar | Jump to a position |

## 💾 Saved data

Your session is saved on exit to a JSON file in your home folder:

```
~/.pro_music_player.json
```

Delete this file to reset the player to a clean state. Music files themselves are never modified or copied.

## ⚠️ Limitations

- **The equaliser bars are simulated.** Pygame cannot expose the real audio spectrum, so the animation reacts to play/pause but not to the music itself.
- **No real equalizer or playback-speed control.** Pygame's mixer doesn't support them. A different backend such as `python-vlc` would be needed.
- **Seeking depends on the format.** It works for mp3 and ogg. For some wav files, seeking may restart the song from the beginning.
- **Album art** is only read from mp3 (ID3) and flac files, and requires Pillow.

## 🛠️ Troubleshooting

| Problem | Fix |
|---|---|
| `Could not start audio device` | Make sure an output device is connected and not exclusively used by another app. |
| `ModuleNotFoundError: No module named 'tkinter'` | Install Tkinter for your OS (see the Linux note above). |
| No album art shown | Install Pillow (`pip install pillow`) and check the file has embedded art. |
| Drag & drop does nothing | Install the optional package: `pip install tkinterdnd2`. |
| Emoji icons look broken | Your system font may lack emoji glyphs. Install a font such as *Segoe UI Emoji* or *Noto Color Emoji*. |

## 🗂️ Project structure

```
pro-music-player/
├── pro_music_player.py   # the entire application
├── requirements.txt
└── README.md
```

## 🤝 Contributing

Contributions are welcome:

1. Fork the repository
2. Create a branch: `git checkout -b feature/my-feature`
3. Commit your changes: `git commit -m "Add my feature"`
4. Push the branch: `git push origin feature/my-feature`
5. Open a pull request

Ideas for future work: lyrics display, a mini-player mode, a VLC backend with a real equalizer and speed control, and extra tag formats (m4a, opus).

## 📄 License

Released under the [MIT License](LICENSE). Add a `LICENSE` file to your repository, or replace this section with your preferred license.
