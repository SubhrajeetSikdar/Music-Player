"""
online_services.py - online helpers for Pro Music Player.

  * SpotifyService      remote-control Spotify (search, playlists, playback) via the Web API
  * AppleMusicService   search / browse Apple Music and open songs in the Apple Music app
  * download_audio      fetch a direct audio link into a local cache so pygame can play it

Everything here is blocking network code: call it from a background thread.

Install:  pip install spotipy pyjwt cryptography
"""

import hashlib
import http.server
import json
import os
import platform
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser

try:
    import spotipy
    from spotipy.oauth2 import SpotifyPKCE
    HAS_SPOTIPY = True
except ImportError:
    HAS_SPOTIPY = False

try:
    import jwt  # PyJWT (+ cryptography for ES256)
    HAS_JWT = True
except ImportError:
    HAS_JWT = False

UA = "ProMusicPlayer/2.0"
SUPPORTED = (".mp3", ".wav", ".ogg", ".flac")
HOME = os.path.expanduser("~")

SPOTIFY_REDIRECT = "http://127.0.0.1:8888/callback"   # register this exact URI in your Spotify app
SPOTIFY_CACHE = os.path.join(HOME, ".pro_music_player_spotify.json")
SPOTIFY_SCOPES = " ".join([
    "user-read-playback-state", "user-modify-playback-state", "user-read-currently-playing",
    "playlist-read-private", "playlist-read-collaborative",
    "user-library-read", "user-library-modify",
])

CACHE_DIR = os.path.join(tempfile.gettempdir(), "pro_music_player_cache")
CONTENT_TYPES = {
    "audio/mpeg": ".mp3", "audio/mp3": ".mp3",
    "audio/ogg": ".ogg", "application/ogg": ".ogg",
    "audio/wav": ".wav", "audio/x-wav": ".wav", "audio/wave": ".wav",
    "audio/flac": ".flac", "audio/x-flac": ".flac",
}


class ServiceError(Exception):
    """A problem worth showing to the user (bad credentials, no device, no network...)."""


# ------------------------------------------------------------------ helpers
def http_json(url, headers=None, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise ServiceError("Apple Music rejected the developer token. Check your Team ID, "
                               "Key ID and .p8 key file.") from e
        if e.code == 403:
            raise ServiceError("Apple Music refused the request (403). For library features, "
                               "sign in again to refresh your user token.") from e
        raise ServiceError(f"Server returned HTTP {e.code}.") from e
    except urllib.error.URLError as e:
        raise ServiceError(f"Network error: {e.reason}. Check your internet connection.") from e


def fetch_bytes(url, timeout=10, max_bytes=5 * 1024 * 1024):
    """Download a small file (album art) into memory."""
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(max_bytes)


def download_audio(url, progress=None, max_mb=200):
    """Download a direct audio link to the cache folder and return the local path."""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ServiceError("Please enter a link starting with http:// or https://")
    os.makedirs(CACHE_DIR, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            ext = os.path.splitext(parsed.path)[1].lower()
            if ext not in SUPPORTED:
                ctype = r.headers.get("Content-Type", "").split(";")[0].strip().lower()
                ext = CONTENT_TYPES.get(ctype)
            if not ext:
                raise ServiceError("That link isn't a direct mp3 / ogg / wav / flac file.")
            dest = os.path.join(CACHE_DIR, hashlib.sha1(url.encode()).hexdigest()[:16] + ext)
            if os.path.exists(dest):
                return dest
            total = int(r.headers.get("Content-Length") or 0)
            limit = max_mb * 1024 * 1024
            if total > limit:
                raise ServiceError(f"File is larger than {max_mb} MB.")
            done = 0
            tmp = dest + ".part"
            with open(tmp, "wb") as f:
                while True:
                    chunk = r.read(64 * 1024)
                    if not chunk:
                        break
                    done += len(chunk)
                    if done > limit:
                        f.close()
                        os.remove(tmp)
                        raise ServiceError(f"Download exceeded {max_mb} MB - this looks like a live "
                                           "stream, which isn't supported.")
                    f.write(chunk)
                    if progress:
                        progress(done, total)
            os.replace(tmp, dest)
            return dest
    except urllib.error.HTTPError as e:
        raise ServiceError(f"Server returned HTTP {e.code}.") from e
    except urllib.error.URLError as e:
        raise ServiceError(f"Network error: {e.reason}") from e


# ------------------------------------------------------------------ Spotify
def _spotify_track(t):
    """Normalise a Spotify track / episode object into the player's dict format."""
    if not t:
        return None
    album = t.get("album") or {}
    imgs = album.get("images") or t.get("images") or []
    artists = t.get("artists") or []
    artist = ", ".join(a.get("name", "") for a in artists) or (t.get("show") or {}).get("name", "")
    return dict(kind="track", uri=t.get("uri"), id=t.get("id"), title=t.get("name", ""),
                artist=artist, album=album.get("name", ""),
                duration=(t.get("duration_ms") or 0) / 1000,
                art=imgs[0]["url"] if imgs else None,
                url=(t.get("external_urls") or {}).get("spotify"))


class SpotifyService:
    """Remote control for Spotify. Audio plays on a Spotify device (desktop app, phone,
    librespot...), NOT inside this program - Spotify does not allow third-party decoding."""

    def __init__(self):
        self.sp = None
        self.user_name = ""

    @property
    def connected(self):
        return self.sp is not None

    # -- connection
    def connect(self, client_id):
        if not HAS_SPOTIPY:
            raise ServiceError("Spotify support needs spotipy:  pip install spotipy")
        auth = SpotifyPKCE(client_id=client_id, redirect_uri=SPOTIFY_REDIRECT,
                           scope=SPOTIFY_SCOPES, cache_path=SPOTIFY_CACHE, open_browser=True)
        sp = spotipy.Spotify(auth_manager=auth, requests_timeout=10)
        try:
            me = sp.current_user()
        except Exception as e:
            raise ServiceError(f"Could not sign in to Spotify: {e}") from e
        self.sp = sp
        self.user_name = me.get("display_name") or me.get("id", "")

    def disconnect(self):
        self.sp = None
        self.user_name = ""
        try:
            os.remove(SPOTIFY_CACHE)
        except OSError:
            pass

    def _explain(self, e):
        text = f"{getattr(e, 'reason', '') or ''} {getattr(e, 'msg', '')}".upper()
        status = getattr(e, "http_status", 0)
        if "NO_ACTIVE_DEVICE" in text:
            return ("No active Spotify device. Open Spotify on your computer or phone (play "
                    "anything once), or use Online > Spotify: choose playback device.")
        if "PREMIUM" in text:
            return "Spotify Premium is required to control playback."
        if status == 401:
            return "Spotify session expired. Use Online > Spotify: connect to sign in again."
        if status == 403:
            return ("Spotify refused the request (403). Playback control needs Premium, and "
                    "apps in Development Mode only work for accounts added under User "
                    "Management in the Spotify developer dashboard.")
        if status == 429:
            return "Spotify rate limit reached. Wait a moment and try again."
        return f"Spotify error: {getattr(e, 'msg', e)}"

    def _call(self, fn, *args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except spotipy.SpotifyException as e:
            raise ServiceError(self._explain(e)) from e
        except Exception as e:
            if isinstance(e, ServiceError):
                raise
            raise ServiceError(f"Spotify request failed: {e}") from e

    # -- browsing
    def search(self, query, pages=2):
        """Tracks + playlists. Dev-mode apps are capped at 10 results per request."""
        tracks, playlists = [], []
        for page in range(pages):
            res = self._call(self.sp.search, q=query, limit=10, offset=page * 10,
                             type="track,playlist")
            tracks += [_spotify_track(t) for t in (res.get("tracks") or {}).get("items", []) if t]
            for p in (res.get("playlists") or {}).get("items", []):
                if p:
                    playlists.append(self._playlist(p))
        return tracks + playlists

    @staticmethod
    def _playlist(p):
        body = p.get("items") or p.get("tracks") or {}
        total = body.get("total", "")
        return dict(kind="playlist", uri=p.get("uri"), id=p.get("id"), title=p.get("name", ""),
                    artist=(p.get("owner") or {}).get("display_name", ""),
                    album=f"{total} tracks" if total != "" else "Playlist", duration=0,
                    art=None, url=(p.get("external_urls") or {}).get("spotify"))

    def my_playlists(self):
        out, offset = [], 0
        while offset < 100:
            res = self._call(self.sp.current_user_playlists, limit=50, offset=offset)
            items = res.get("items", [])
            out += [self._playlist(p) for p in items if p]
            if len(items) < 50:
                break
            offset += 50
        return out

    def playlist_tracks(self, playlist_id):
        out, offset = [], 0
        try:
            while offset < 200:
                res = self._call(self.sp._get, f"playlists/{playlist_id}/items",
                                 limit=50, offset=offset)
                items = res.get("items", [])
                for entry in items:
                    t = entry.get("item") or entry.get("track")
                    if t and t.get("type", "track") == "track":
                        out.append(_spotify_track(t))
                if len(items) < 50:
                    break
                offset += 50
        except ServiceError as e:
            if "403" in str(e):
                raise ServiceError("Spotify only lets this app read the tracks of playlists you "
                                   "own or collaborate on. You can still Play the playlist.") from e
            raise
        return out

    def saved_tracks(self):
        out, offset = [], 0
        while offset < 100:
            res = self._call(self.sp.current_user_saved_tracks, limit=50, offset=offset)
            items = res.get("items", [])
            out += [_spotify_track(i.get("track")) for i in items if i.get("track")]
            if len(items) < 50:
                break
            offset += 50
        return out

    # -- devices & playback
    def devices(self):
        return self._call(self.sp.devices).get("devices", [])

    def transfer(self, device_id):
        self._call(self.sp.transfer_playback, device_id, force_play=True)

    def play(self, uris=None, context_uri=None):
        kw = {}
        if uris:
            kw["uris"] = uris
        if context_uri:
            kw["context_uri"] = context_uri
        self._call(self.sp.start_playback, **kw)

    def resume(self):
        self._call(self.sp.start_playback)

    def pause(self):
        self._call(self.sp.pause_playback)

    def next(self):
        self._call(self.sp.next_track)

    def previous(self):
        self._call(self.sp.previous_track)

    def seek(self, ms):
        self._call(self.sp.seek_track, int(ms))

    def set_volume(self, pct):
        self._call(self.sp.volume, int(pct))

    def set_shuffle(self, on):
        self._call(self.sp.shuffle, bool(on))

    def set_repeat(self, mode):          # "off" | "context" | "track"
        self._call(self.sp.repeat, mode)

    def add_to_queue(self, uri):
        self._call(self.sp.add_to_queue, uri)

    def like(self, uri):
        self._call(self.sp._put, "me/library", payload={"uris": [uri]})

    def current(self):
        """Snapshot of what Spotify is playing right now (or None)."""
        pb = self._call(self.sp.current_playback)
        if not pb or not pb.get("item"):
            return None
        dev = pb.get("device") or {}
        return dict(is_playing=bool(pb.get("is_playing")),
                    pos=(pb.get("progress_ms") or 0) / 1000,
                    track=_spotify_track(pb["item"]),
                    shuffle=bool(pb.get("shuffle_state")),
                    repeat=pb.get("repeat_state", "off"),
                    device=dev.get("name", ""))


# ------------------------------------------------------------------ Apple Music
APPLE_AUTH_PAGE = """<!doctype html><meta charset="utf-8"><title>Pro Music Player - Apple Music</title>
<body style="font-family:system-ui,sans-serif;max-width:520px;margin:70px auto;text-align:center">
<h2>Connect Apple Music</h2>
<p id="msg">Loading MusicKit...</p>
<button id="go" disabled style="font-size:18px;padding:10px 26px">Authorize</button>
<script src="https://js-cdn.music.apple.com/musickit/v3/musickit.js" async></script>
<script>
const msg = t => document.getElementById('msg').textContent = t;
document.addEventListener('musickitloaded', async () => {
  try {
    await MusicKit.configure({developerToken: '__DEV_TOKEN__',
                              app: {name: 'Pro Music Player', build: '2.0'}});
    msg('Click Authorize and sign in with your Apple ID.');
    document.getElementById('go').disabled = false;
  } catch (e) { msg('MusicKit failed to start: ' + e); }
});
document.getElementById('go').onclick = async () => {
  try {
    const token = await MusicKit.getInstance().authorize();
    await fetch('/token', {method: 'POST', headers: {'Content-Type': 'application/json'},
                           body: JSON.stringify({token})});
    msg('Done! You can close this tab and go back to the player.');
  } catch (e) { msg('Authorization failed: ' + e); }
};
</script></body>"""


def open_in_apple_music(url):
    """Open a music.apple.com link in the Music app (macOS) or the default browser."""
    if platform.system() == "Darwin" and url.startswith("https://music.apple.com"):
        subprocess.Popen(["open", url.replace("https://", "music://", 1)])
    else:
        webbrowser.open(url)


class AppleMusicService:
    """Apple Music catalogue search + library browsing.

    Playback is not possible from Python (Apple only allows it through MusicKit in an Apple
    app or browser), so songs are opened in the Apple Music app instead.
    Without developer credentials, search falls back to the free iTunes Search API."""

    API = "https://api.music.apple.com/v1"

    def __init__(self, cfg):
        self.cfg = cfg           # shared settings dict (apple_team_id, apple_key_id, ...)
        self._dev = None
        self._dev_key = None
        self._dev_exp = 0

    # -- config helpers
    @property
    def storefront(self):
        return (self.cfg.get("apple_storefront") or "us").lower()

    @property
    def user_token(self):
        return self.cfg.get("apple_user_token", "")

    def has_credentials(self):
        c = self.cfg
        return bool(c.get("apple_team_id") and c.get("apple_key_id")
                    and c.get("apple_key_path") and os.path.exists(c["apple_key_path"]))

    def reset(self):
        self._dev = None

    def developer_token(self):
        if not HAS_JWT:
            raise ServiceError("Apple Music API support needs:  pip install pyjwt cryptography")
        if not self.has_credentials():
            raise ServiceError("Apple Music developer credentials are not set "
                               "(Online > Apple Music: set developer credentials).")
        c = self.cfg
        ident = (c["apple_team_id"], c["apple_key_id"], c["apple_key_path"])
        if self._dev and self._dev_key == ident and time.time() < self._dev_exp - 3600:
            return self._dev
        with open(c["apple_key_path"], "r", encoding="utf-8") as f:
            key = f.read()
        now = int(time.time())
        self._dev_exp = now + 60 * 60 * 24 * 90
        try:
            tok = jwt.encode({"iss": c["apple_team_id"], "iat": now, "exp": self._dev_exp},
                             key, algorithm="ES256", headers={"kid": c["apple_key_id"]})
        except Exception as e:
            raise ServiceError(f"Could not sign the developer token: {e}") from e
        self._dev = tok.decode() if isinstance(tok, bytes) else tok
        self._dev_key = ident
        return self._dev

    def _request(self, path, params=None, user=False):
        url = self.API + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        headers = {"Authorization": f"Bearer {self.developer_token()}"}
        if user:
            if not self.user_token:
                raise ServiceError("Sign in first: Online > Apple Music: sign in.")
            headers["Music-User-Token"] = self.user_token
        return http_json(url, headers)

    # -- mapping
    def _song(self, d):
        a = d.get("attributes", {})
        art = ((a.get("artwork") or {}).get("url") or "").replace("{w}", "300").replace("{h}", "300")
        pp = a.get("playParams") or {}
        cid = pp.get("catalogId") or (d.get("id") if d.get("type") == "songs" else None)
        url = a.get("url") or (f"https://music.apple.com/{self.storefront}/song/{cid}" if cid else None)
        return dict(kind="track", id=d.get("id"), uri=None, title=a.get("name", ""),
                    artist=a.get("artistName", ""), album=a.get("albumName", ""),
                    duration=(a.get("durationInMillis") or 0) / 1000, art=art or None, url=url)

    def _playlist(self, d, lib):
        a = d.get("attributes", {})
        return dict(kind="playlist", id=d.get("id"), uri=None, title=a.get("name", ""),
                    artist=a.get("curatorName", ""), duration=0, art=None, lib=lib,
                    album="Library playlist" if lib else "Playlist", url=a.get("url"))

    # -- browsing
    def search(self, term):
        if self.has_credentials() and HAS_JWT:
            data = self._request(f"/catalog/{self.storefront}/search",
                                 {"term": term, "types": "songs,playlists", "limit": 25})
            res = data.get("results", {})
            out = [self._song(s) for s in (res.get("songs") or {}).get("data", [])]
            out += [self._playlist(p, False) for p in (res.get("playlists") or {}).get("data", [])]
            return out
        # No credentials: free iTunes Search API (songs only)
        data = http_json("https://itunes.apple.com/search?" + urllib.parse.urlencode(
            {"term": term, "media": "music", "entity": "song", "limit": 25,
             "country": self.storefront.upper()}))
        return [dict(kind="track", id=r.get("trackId"), uri=None, title=r.get("trackName", ""),
                     artist=r.get("artistName", ""), album=r.get("collectionName", ""),
                     duration=(r.get("trackTimeMillis") or 0) / 1000,
                     art=r.get("artworkUrl100"), url=r.get("trackViewUrl"))
                for r in data.get("results", []) if r.get("trackName")]

    def library_playlists(self):
        data = self._request("/me/library/playlists", {"limit": 100}, user=True)
        return [self._playlist(p, True) for p in data.get("data", [])]

    def library_songs(self):
        data = self._request("/me/library/songs", {"limit": 100}, user=True)
        return [self._song(s) for s in data.get("data", [])]

    def playlist_tracks(self, item):
        if item.get("lib"):
            data = self._request(f"/me/library/playlists/{item['id']}/tracks",
                                 {"limit": 100}, user=True)
        else:
            data = self._request(f"/catalog/{self.storefront}/playlists/{item['id']}/tracks",
                                 {"limit": 100})
        return [self._song(s) for s in data.get("data", [])]

    # -- user sign-in via a tiny local web page running MusicKit JS
    def authorize_user(self, timeout=180):
        page = APPLE_AUTH_PAGE.replace("__DEV_TOKEN__", self.developer_token()).encode("utf-8")
        result = {}

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(page)))
                self.end_headers()
                self.wfile.write(page)

            def do_POST(self):
                try:
                    size = min(int(self.headers.get("Content-Length", 0)), 8192)
                    result["token"] = json.loads(self.rfile.read(size)).get("token", "")
                except Exception:
                    pass
                self.send_response(200)
                self.end_headers()

            def log_message(self, *args):
                pass

        try:
            srv = http.server.HTTPServer(("127.0.0.1", 8765), Handler)
        except OSError as e:
            raise ServiceError(f"Could not open local port 8765: {e}") from e
        srv.timeout = 1
        webbrowser.open("http://127.0.0.1:8765/")
        end = time.time() + timeout
        try:
            while time.time() < end and not result.get("token"):
                srv.handle_request()
        finally:
            srv.server_close()
        if not result.get("token"):
            raise ServiceError("Apple Music sign-in timed out or was cancelled.")
        return result["token"]
