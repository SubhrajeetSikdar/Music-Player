# 🎧 Pro Music Player

A feature-rich desktop music player written in Python with **Tkinter** and **Pygame**. It has a library view, a play queue, seekable playback, album art, themes and a lot of keyboard and mouse shortcuts, and it remembers your session between launches. It can also search **Spotify** and **Apple Music** and play audio from web links.

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

**Online (new)**
- **Spotify:** search tracks and playlists, browse your playlists and liked songs, and use the player as a remote control (play, pause, next, previous, seek, volume, shuffle, repeat, add to queue, like). Audio plays on a Spotify device such as the desktop app or your phone.
- **Apple Music:** search the catalogue (works with no sign-in via the free iTunes Search API), browse your library playlists and songs (with developer credentials), and open songs in the Apple Music app.
- **Play from URL:** paste a direct link to an mp3, ogg, wav or flac file and it is downloaded and played.
- All network calls run in background threads, so the window never freezes.

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

**Requirements:** Python 3.8 or newer. Keep `pro_music_player.py` and `online_services.py` in the same folder.

```bash
git clone https://github.com/<your-username>/pro-music-player.git
cd pro-music-player
pip install -r requirements.txt
python pro_music_player.py
```

Or install the dependencies manually:

```bash
pip install pygame mutagen pillow
pip install spotipy pyjwt cryptography   # Spotify + Apple Music
pip install tkinterdnd2                   # optional: drag & drop support
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

## 🌐 Online setup

All online features live in the **Online** tab and the **Online** menu.

### Spotify

1. You need a **Spotify Premium** account. Spotify requires Premium both to create a developer app and to control playback.
2. Go to the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard), create an app and choose **Web API**.
3. In the app settings add this exact Redirect URI: `http://127.0.0.1:8888/callback`
4. In the player choose **Online ▸ Spotify: set Client ID…** and paste the Client ID. No client secret is needed (the app uses the PKCE sign-in flow).
5. Search in the Online tab. The first time, your browser opens so you can approve access.
6. Open Spotify on your computer or phone and play something once, so there is an active device. Use **Online ▸ Spotify: choose playback device…** to switch devices.

Spotify rules that affect this app (as of the February 2026 changes):
- Apps in Development Mode work only for the app owner plus up to 5 users you add under *User Management* in the dashboard.
- Search returns at most 10 results per request, so the player makes two requests and shows up to 20 tracks.
- The tracks inside a playlist can only be listed for playlists you own or collaborate on. Other playlists can still be played with **Play**.

### Apple Music

- **No setup needed for search.** Without credentials the player uses the free iTunes Search API. Results open in the Apple Music app (or your browser).
- **For catalogue search through the official API and your own library** you need a paid [Apple Developer Program](https://developer.apple.com/programs/) membership:
  1. Create a **MusicKit key** and download the `.p8` file. Note your **Team ID** and the **Key ID**.
  2. Choose **Online ▸ Apple Music: set developer credentials…** and enter the Team ID, Key ID, the `.p8` file and your storefront (a two-letter country code such as `us`).
  3. For library access choose **Online ▸ Apple Music: sign in…**. A page opens in your browser where you approve access with your Apple ID.

### Play from URL

Choose **Online ▸ Play audio from URL…** and paste a direct link to an audio file. Files are downloaded to a temporary cache (200 MB limit) and added to your library.

## 💾 Saved data

Your session is saved on exit to a JSON file in your home folder:

```
~/.pro_music_player.json            # settings, library, and online credentials
~/.pro_music_player_spotify.json    # Spotify sign-in token cache
```

The first file may contain your Apple Music user token and Spotify Client ID, so the player restricts it to your user account where the OS supports that. Do not share or commit these files. Delete them to reset the player or sign out. Music files themselves are never modified or copied.

## ⚠️ Limitations

- **Spotify audio is not played inside this app.** Spotify does not allow third-party apps to decode its streams, so the player controls a Spotify device instead. The seek bar, volume, shuffle and repeat all control that device.
- **Apple Music songs are not played inside this app either.** Apple only allows playback through MusicKit in its own apps or a browser, so songs are opened in the Apple Music app.
- **The local play queue, favourites and play counts apply to local files only.** In Spotify mode the Spotify queue is used.
- **Web links must be direct audio files.** Live radio streams and pages like YouTube are not supported.
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
| Spotify: `INVALID_CLIENT: Invalid redirect URI` | The Redirect URI in the dashboard must be exactly `http://127.0.0.1:8888/callback`. |
| Spotify: `No active device` | Open Spotify on any device and play a song once, or use **Choose playback device**. |
| Spotify: 403 errors | Check that the app owner has Premium and that your account is listed under *User Management*. |
| Apple Music: developer token rejected | Check the Team ID, Key ID and that the `.p8` file matches that Key ID. |
| Apple Music sign-in page fails | Try another browser, and make sure port 8765 is free. Sign-in is the least-tested part of the app. |
| Drag & drop does nothing | Install the optional package: `pip install tkinterdnd2`. |
| Emoji icons look broken | Your system font may lack emoji glyphs. Install a font such as *Segoe UI Emoji* or *Noto Color Emoji*. |

## 🗂️ Project structure

```
pro-music-player/
├── pro_music_player.py   # the player (UI, local playback)
├── online_services.py    # Spotify, Apple Music and URL download helpers
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

Ideas for future work: lyrics display, a mini-player mode, a VLC backend with a real equalizer and speed control, extra tag formats (m4a, opus), and internet radio streaming.

## 📄 License

Released under the [MIT License](LICENSE). Add a `LICENSE` file to your repository, or replace this section with your preferred license.
