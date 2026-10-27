#!/usr/bin/env python3
"""
Open Rails for macOS: launcher menu.

The Windows Open Rails Menu.exe is built on Windows Forms and does not run on macOS. This is a small
replacement: it serves a local web page, lets you pick a route and an Activity or an Explore run
(consist, path, time, season, weather) and a few display options, then starts the native macOS
RunActivity build.

Run it with "Open Rails Menu.command" (double-click) or: python3 orts-menu.py
Needs only Python 3 (included with the Xcode Command Line Tools), no extra packages.
"""

import collections
import http.server
import json
import os
import re
import secrets
import shutil
import socketserver
import subprocess
import sys
import threading
import urllib.parse
import webbrowser

HOME = os.path.expanduser("~")
HERE = os.path.dirname(os.path.abspath(__file__))
PORTS = range(7788, 7799)
DRY_RUN = bool(os.environ.get("ORTS_DRY_RUN"))
CONFIG_PATH = os.path.join(HOME, ".openrails-mac-menu.json")
TOKEN = secrets.token_hex(16)


# --------------------------------------------------------------------------------------------
# Locating things
# --------------------------------------------------------------------------------------------

def find_program_dir():
    """The folder that contains RunActivity.dll (next to this script, or one level up)."""
    candidates = [
        os.environ.get("ORTS_PROGRAM_DIR"),
        os.path.join(HERE, "Program"),
        os.path.join(HERE, "..", "Program"),
    ]
    for c in candidates:
        if c and os.path.isfile(os.path.join(c, "RunActivity.dll")):
            return os.path.abspath(c)
    return os.path.abspath(next(c for c in candidates[1:] if c))


PROGRAM_DIR = find_program_dir()
RUNACTIVITY_DLL = os.path.join(PROGRAM_DIR, "RunActivity.dll")
INI_PATH = os.path.join(PROGRAM_DIR, "OpenRails.ini")


def find_dotnet():
    found = shutil.which("dotnet")
    if found:
        return found
    for c in ("/opt/homebrew/bin/dotnet", "/usr/local/share/dotnet/dotnet", "/usr/local/bin/dotnet",
              os.path.join(HOME, ".dotnet", "dotnet")):
        if os.path.isfile(c) and os.access(c, os.X_OK):
            return c
    return None


def ci_child(parent, name):
    """Case-insensitive lookup of a child (MSTS content mixes ROUTES / Routes / routes)."""
    try:
        for entry in os.listdir(parent):
            if entry.lower() == name.lower():
                return os.path.join(parent, entry)
    except OSError:
        pass
    return None


def list_files(directory, extension):
    try:
        names = [f for f in os.listdir(directory)
                 if f.lower().endswith(extension) and not f.startswith(".")]
    except OSError:
        return []
    return sorted(names, key=lambda s: s.lower())


# --------------------------------------------------------------------------------------------
# Content folders
# --------------------------------------------------------------------------------------------

DEFAULT_ROOTS = [
    os.path.join(HOME, "MSTS"),
    os.path.join(HOME, "Documents", "MSTS"),
    os.path.join(HOME, "Open Rails"),
    os.path.join(HOME, "Documents", "Open Rails"),
    os.path.join(HOME, "Games", "MSTS"),
    "/Users/Shared/MSTS",
]


def load_config():
    try:
        with open(CONFIG_PATH, "r") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_config(cfg):
    try:
        with open(CONFIG_PATH, "w") as f:
            json.dump(cfg, f, indent=2)
    except OSError:
        pass


def all_roots():
    roots = []
    roots += [r for r in load_config().get("content_roots", []) if isinstance(r, str)]
    roots += [r for r in os.environ.get("ORTS_CONTENT", "").split(os.pathsep) if r]
    roots += DEFAULT_ROOTS
    seen, result = set(), []
    for r in roots:
        r = os.path.abspath(os.path.expanduser(r))
        if r not in seen and ci_child(r, "routes"):
            seen.add(r)
            result.append(r)
    return result


def clean(name):
    return os.path.splitext(name)[0].replace("_", " ").strip()


def route_title(route_dir, folder):
    """Best effort: the route's display name from its .trk file, else the folder name."""
    for trk in list_files(route_dir, ".trk")[:1]:
        try:
            with open(os.path.join(route_dir, trk), "rb") as f:
                raw = f.read(8192)
            if raw[:2] == b"\xff\xfe":
                text = raw.decode("utf-16", "ignore")
            else:
                text = raw.decode("utf-8", "ignore")
            m = re.search(r"\bName\s*\(", text)
            if m:
                depth, i = 1, m.end()
                while i < len(text) and depth:  # names can contain brackets, e.g. "KonkanIR (Electric)"
                    depth += {"(": 1, ")": -1}.get(text[i], 0)
                    i += 1
                title = text[m.end():i - 1].strip().strip('"').strip() if depth == 0 else ""
                if title:
                    return title
        except OSError:
            pass
    return clean(folder)


def scan():
    """All routes found in all content folders, each with its activities, paths and consists."""
    routes = []
    for root in all_roots():
        routes_dir = ci_child(root, "routes")
        trains_dir = ci_child(root, "trains")
        consists_dir = ci_child(trains_dir, "consists") if trains_dir else None
        consists = list_files(consists_dir, ".con") if consists_dir else []
        for folder in sorted(os.listdir(routes_dir), key=lambda s: s.lower()):
            route_dir = os.path.join(routes_dir, folder)
            if not os.path.isdir(route_dir) or folder.startswith("."):
                continue
            paths_dir = ci_child(route_dir, "paths")
            acts_dir = ci_child(route_dir, "activities")
            paths = list_files(paths_dir, ".pat") if paths_dir else []
            acts = list_files(acts_dir, ".act") if acts_dir else []
            if not paths and not acts:
                continue  # not a playable route folder
            title = route_title(route_dir, folder)
            routes.append({
                "root": root,
                "title": title if title.lower() == folder.lower() else "%s  [%s]" % (title, folder),
                "activities": [{"file": os.path.join(acts_dir, a), "title": clean(a)} for a in acts],
                "paths": [{"file": os.path.join(paths_dir, p), "title": clean(p)} for p in paths],
                "consists": [{"file": os.path.join(consists_dir, c), "title": clean(c)} for c in consists],
            })
    return routes


# --------------------------------------------------------------------------------------------
# OpenRails.ini (the few display options this menu exposes)
# --------------------------------------------------------------------------------------------

OPTION_DEFAULTS = {"FullScreen": True, "Letterbox2DCab": False, "WindowSize": "1024x768"}


def read_ini():
    try:
        with open(INI_PATH, "rb") as f:
            raw = f.read()
    except OSError:
        return "", False
    bom = raw.startswith(b"\xef\xbb\xbf")
    return raw[3:].decode("utf-8", "replace") if bom else raw.decode("utf-8", "replace"), bom


def current_options():
    text, _ = read_ini()
    values = dict(OPTION_DEFAULTS)
    for line in text.splitlines():
        key, sep, val = line.partition("=")
        key = key.strip()
        if sep and key in OPTION_DEFAULTS:
            kind, _, payload = val.strip().partition(":")
            if kind == "bool":
                values[key] = payload.strip().lower() == "true"
            elif kind == "string":
                values[key] = urllib.parse.unquote(payload)
    return values


def format_option(key, value):
    if key in ("FullScreen", "Letterbox2DCab"):
        return "bool:true" if value else "bool:false"
    return "string:" + urllib.parse.quote(str(value), safe="")


def write_options(options):
    """Set only the given keys in OpenRails.ini; everything else in the file is left untouched."""
    text, bom = read_ini()
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines()
    for key, value in options.items():
        new_line = "%s=%s" % (key, format_option(key, value))
        for i, line in enumerate(lines):
            if line.partition("=")[0].strip() == key:
                lines[i] = new_line
                break
        else:
            header = next((i for i, l in enumerate(lines) if l.strip().lower() == "[orts]"), None)
            if header is None:
                lines[0:0] = ["[ORTS]"]
                header = 0
            lines.insert(header + 1, new_line)
    data = newline.join(lines) + newline
    with open(INI_PATH, "wb") as f:
        f.write((b"\xef\xbb\xbf" if bom or not text else b"") + data.encode("utf-8"))


def validated_options(req):
    """Only allow the exact options and value shapes this menu knows about."""
    out = {}
    for key in ("FullScreen", "Letterbox2DCab"):
        if isinstance(req.get(key), bool):
            out[key] = req[key]
    size = req.get("WindowSize")
    if isinstance(size, str) and re.match(r"^\d{3,5}x\d{3,5}$", size):
        out["WindowSize"] = size
    return out


# --------------------------------------------------------------------------------------------
# Setup check, launching, status
# --------------------------------------------------------------------------------------------

def setup_checks():
    dotnet = find_dotnet()
    shader = os.path.join(PROGRAM_DIR, "Content", "Loading.mgfx")
    native = ci_child(os.path.join(PROGRAM_DIR, "runtimes", "osx", "native"), "libSDL2-2.0.0.dylib")
    return [
        {"ok": bool(dotnet), "label": ".NET runtime",
         "fix": "Install it with: brew install dotnet"},
        {"ok": os.path.isfile(RUNACTIVITY_DLL), "label": "Open Rails program files",
         "fix": "RunActivity.dll was not found. Use the downloaded release zip, not the source code."},
        {"ok": os.path.isfile(shader), "label": "Compiled shaders",
         "fix": "Program/Content/Loading.mgfx is missing (black screen). Use the downloaded release zip."},
        {"ok": bool(native), "label": "Native libraries (SDL2)",
         "fix": "Program/runtimes/osx/native is incomplete. Download the release zip again."},
        {"ok": bool(all_roots()), "label": "Route content (MSTS / Open Rails)",
         "fix": "No content found. Put it in ~/MSTS (folders ROUTES, TRAINS, GLOBAL) or enter its folder below."},
    ]


class Game(object):
    def __init__(self):
        self.proc = None
        self.output = collections.deque(maxlen=60)
        self.lock = threading.Lock()

    def running(self):
        return self.proc is not None and self.proc.poll() is None

    def _pump(self, proc):
        for line in proc.stdout:
            with self.lock:
                self.output.append(line.rstrip("\n"))

    def start(self, args):
        dotnet = find_dotnet()
        if not dotnet:
            return False, "The .NET runtime was not found. Install it with: brew install dotnet"
        if not os.path.isfile(RUNACTIVITY_DLL):
            return False, "RunActivity.dll was not found next to the menu."
        if self.running():
            return False, "Open Rails is already running."
        cmd = [dotnet, "exec", "--roll-forward", "LatestMajor", RUNACTIVITY_DLL] + args
        if DRY_RUN:
            return True, cmd
        env = dict(os.environ)
        env["DYLD_LIBRARY_PATH"] = "/opt/homebrew/lib:" + env.get("DYLD_LIBRARY_PATH", "")
        self.output.clear()
        self.proc = subprocess.Popen(cmd, cwd=PROGRAM_DIR, env=env, stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT, universal_newlines=True, errors="replace")
        threading.Thread(target=self._pump, args=(self.proc,), daemon=True).start()
        return True, cmd

    def status(self):
        if self.proc is None:
            return {"state": "idle"}
        code = self.proc.poll()
        if code is None:
            return {"state": "running"}
        with self.lock:
            tail = list(self.output)[-25:]
        return {"state": "exited", "code": code, "tail": tail}


GAME = Game()
SNAPSHOT = {"routes": []}


def build_args(req):
    """Turn a menu selection into RunActivity arguments. Returns (args, error)."""
    routes = SNAPSHOT["routes"]
    try:
        route = routes[int(req["route"])]
        if req.get("mode") == "activity":
            return ["-start", "-activity", route["activities"][int(req["activity"])]["file"]], None
        time_value = str(req.get("time", "12:00:00"))
        season, weather = str(req.get("season", "1")), str(req.get("weather", "0"))
        if not re.match(r"^\d{1,2}:\d{2}(:\d{2})?$", time_value) or season not in "0123" \
                or weather not in "012" or len(season) != 1 or len(weather) != 1:
            return None, "Invalid time, season or weather."
        if time_value.count(":") == 1:  # the time picker gives HH:MM
            time_value += ":00"
        return ["-start", "-explorer", route["paths"][int(req["path"])]["file"],
                route["consists"][int(req["consist"])]["file"], time_value, season, weather], None
    except (KeyError, IndexError, ValueError, TypeError):
        return None, "Please choose a route, and a path and consist (or an activity)."


# --------------------------------------------------------------------------------------------
# Web page
# --------------------------------------------------------------------------------------------

PAGE = r"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Open Rails for macOS</title>
<style>
  :root { --bg:#1e2430; --panel:#2b3446; --accent:#e8a33d; --text:#e6ebf2; --muted:#8b97a8; --bad:#e5654d; --ok:#5cc48a; }
  * { box-sizing:border-box; font-family:-apple-system,'Segoe UI',Helvetica,Arial,sans-serif; }
  body { margin:0; background:linear-gradient(160deg,#161b24,#232c3c); color:var(--text); min-height:100vh;
         display:flex; justify-content:center; padding:28px 12px; }
  .card { background:var(--panel); width:600px; border-radius:14px; padding:0 0 26px; height:fit-content;
          box-shadow:0 24px 60px rgba(0,0,0,.55); overflow:hidden; }
  .hdr { background:linear-gradient(90deg,#c8412b,#e8a33d); padding:20px 28px; }
  .hdr h1 { margin:0; font-size:24px; color:#fff; }
  .hdr p { margin:4px 0 0; color:rgba(255,255,255,.85); font-size:13px; }
  .body { padding:18px 28px 0; }
  label { display:block; font-size:12px; text-transform:uppercase; letter-spacing:.6px; color:var(--muted); margin:16px 0 6px; }
  select, input[type=text], input[type=time] { width:100%; background:#212a39; color:var(--text); border:1px solid #3a465b;
                            border-radius:8px; padding:10px 12px; font-size:15px; color-scheme:dark; }
  select:focus, input:focus { outline:none; border-color:var(--accent); }
  .row { display:flex; gap:12px; } .row > div { flex:1; }
  .modebtns { display:flex; margin-top:6px; border:1px solid #3a465b; border-radius:8px; overflow:hidden; }
  .modebtns button { flex:1; background:#212a39; color:var(--muted); border:none; padding:11px; font-size:14px; cursor:pointer; }
  .modebtns button.active { background:var(--accent); color:#1a1f29; font-weight:600; }
  .start { margin-top:24px; width:100%; background:var(--accent); color:#1a1f29; border:none; border-radius:8px;
           padding:15px; font-size:17px; font-weight:700; cursor:pointer; }
  .start:disabled { opacity:.5; cursor:default; }
  .small { background:#3a465b; color:var(--text); border:none; border-radius:8px; padding:11px 16px; cursor:pointer; }
  .hint { color:var(--muted); font-size:12px; margin-top:14px; line-height:1.5; }
  .hidden { display:none; }
  .check { font-size:13px; margin:3px 0; } .check.ok { color:var(--ok); } .check.bad { color:var(--bad); }
  .check small { display:block; color:var(--muted); margin-left:20px; }
  #status { margin-top:14px; font-size:14px; min-height:20px; }
  pre { background:#161b24; padding:10px; border-radius:8px; font-size:11px; overflow:auto; max-height:200px; white-space:pre-wrap; }
  .opt { display:flex; align-items:center; gap:8px; margin:8px 0; font-size:14px; }
  details summary { cursor:pointer; color:var(--muted); font-size:13px; margin-top:18px; }
</style></head>
<body>
  <div class="card">
    <div class="hdr"><h1>Open Rails</h1><p>macOS edition, native Apple Silicon</p></div>
    <div class="body">
      <div id="checks"></div>

      <details id="folder"><summary>Route content folder</summary>
        <label>Folder that contains ROUTES, TRAINS and GLOBAL</label>
        <div class="row"><div><input type="text" id="root" placeholder="/Users/you/MSTS"></div>
          <div style="flex:0"><button class="small" onclick="addRoot()">Use</button></div></div>
        <div class="hint" id="rootmsg"></div>
      </details>

      <label>Route</label>
      <select id="route"></select>

      <label>Mode</label>
      <div class="modebtns">
        <button id="mAct" onclick="setMode('activity')">Activity</button>
        <button id="mExp" class="active" onclick="setMode('explore')">Explore</button>
      </div>

      <div id="actBox" class="hidden">
        <label>Activity</label><select id="activity"></select>
      </div>
      <div id="expBox">
        <label>Consist (train)</label><select id="consist"></select>
        <label>Path</label><select id="path"></select>
        <div class="row">
          <div><label>Time</label><input type="time" id="time" value="12:00"></div>
          <div><label>Season</label><select id="season">
            <option value="1">Summer</option><option value="0">Spring</option>
            <option value="2">Autumn</option><option value="3">Winter</option></select></div>
          <div><label>Weather</label><select id="weather">
            <option value="0">Clear</option><option value="1">Snow</option><option value="2">Rain</option></select></div>
        </div>
      </div>

      <details><summary>Display options</summary>
        <div class="opt"><input type="checkbox" id="fullscreen"><span>Full screen</span></div>
        <div class="opt"><input type="checkbox" id="letterbox"><span>Show the whole 2D cab (black bars instead of cropping)</span></div>
        <label>Window size (used when not full screen)</label>
        <input type="text" id="wsize" placeholder="1280x720">
      </details>

      <button class="start" id="start" onclick="startGame()">START</button>
      <div id="status"></div>
      <pre id="tail" class="hidden"></pre>
      <div class="hint">Loading a big route can take a few minutes. In game: W / S = throttle, arrow keys = camera, 1 to 5 = views, F1 = help.</div>
    </div>
  </div>
<script>
const TOKEN = "__TOKEN__";
let DATA = [], mode = 'explore';
const $ = id => document.getElementById(id);
async function api(path, body) {
  const r = await fetch(path, {method: body ? 'POST' : 'GET',
    headers: {'X-ORTS-Token': TOKEN, 'Content-Type': 'application/json'}, body: body ? JSON.stringify(body) : undefined});
  return r.json();
}
function fill(select, items) {
  select.textContent = '';
  items.forEach((it, i) => { const o = document.createElement('option'); o.value = i; o.textContent = it.title; select.appendChild(o); });
}
function setMode(m) {
  mode = m;
  $('mAct').classList.toggle('active', m === 'activity'); $('mExp').classList.toggle('active', m === 'explore');
  $('actBox').classList.toggle('hidden', m !== 'activity'); $('expBox').classList.toggle('hidden', m !== 'explore');
}
function fillRoute() {
  const r = DATA[+$('route').value]; if (!r) return;
  fill($('activity'), r.activities); fill($('consist'), r.consists); fill($('path'), r.paths);
  if (!r.paths.length && r.activities.length) setMode('activity');
}
function renderChecks(checks) {
  const box = $('checks'); box.textContent = '';
  const bad = checks.filter(c => !c.ok);
  if (!bad.length) { const d = document.createElement('div'); d.className = 'check ok'; d.textContent = 'Setup OK'; box.appendChild(d); return; }
  checks.forEach(c => {
    const d = document.createElement('div'); d.className = 'check ' + (c.ok ? 'ok' : 'bad');
    d.textContent = (c.ok ? '✓ ' : '✗ ') + c.label;
    if (!c.ok) { const s = document.createElement('small'); s.textContent = c.fix; d.appendChild(s); }
    box.appendChild(d);
  });
}
async function load() {
  const info = await api('/api/info');
  renderChecks(info.checks);
  DATA = info.routes; fill($('route'), DATA); fillRoute();
  $('fullscreen').checked = info.options.FullScreen; $('letterbox').checked = info.options.Letterbox2DCab;
  $('wsize').value = info.options.WindowSize;
  if (!DATA.length) $('folder').open = true;
  $('rootmsg').textContent = info.roots.length ? 'Using: ' + info.roots.join(', ') : 'No content folder found yet.';
}
async function addRoot() {
  const res = await api('/api/root', {path: $('root').value});
  $('rootmsg').textContent = res.error || 'Added.'; if (!res.error) load();
}
async function startGame() {
  const body = {route: $('route').value, mode: mode, activity: $('activity').value, consist: $('consist').value,
    path: $('path').value, time: $('time').value, season: $('season').value, weather: $('weather').value,
    FullScreen: $('fullscreen').checked, Letterbox2DCab: $('letterbox').checked, WindowSize: $('wsize').value};
  $('status').textContent = 'Starting...'; $('tail').classList.add('hidden');
  const res = await api('/api/start', body);
  if (res.error) { $('status').textContent = res.error; return; }
  $('start').disabled = true; $('status').textContent = 'Open Rails is starting. A game window will open; loading can take a few minutes.';
  poll();
}
async function poll() {
  const s = await api('/api/status');
  if (s.state === 'running') { setTimeout(poll, 2000); return; }
  $('start').disabled = false;
  if (s.state === 'exited') {
    if (s.code === 0) { $('status').textContent = 'Open Rails closed.'; return; }
    $('status').textContent = 'Open Rails stopped with an error (code ' + s.code + '). See OpenRailsLog.txt on your Desktop.';
    $('tail').textContent = s.tail.join('\n'); $('tail').classList.remove('hidden');
  }
}
$('route').addEventListener('change', fillRoute);
load(); setMode('explore');
</script></body></html>"""


# --------------------------------------------------------------------------------------------
# HTTP server (local only; every API call needs the per-run token)
# --------------------------------------------------------------------------------------------

class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json"):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj))

    def _host_ok(self):
        # Refuse requests that were not addressed to us as localhost (DNS rebinding protection).
        host = (self.headers.get("Host") or "").rsplit(":", 1)[0]
        return host in ("127.0.0.1", "localhost")

    def _api_ok(self):
        return self._host_ok() and secrets.compare_digest(self.headers.get("X-ORTS-Token", ""), TOKEN)

    def do_GET(self):
        if not self._host_ok():
            return self._send(403, "forbidden", "text/plain")
        if self.path in ("/", "/index.html"):
            return self._send(200, PAGE.replace("__TOKEN__", TOKEN), "text/html")
        if not self._api_ok():
            return self._json({"error": "forbidden"}, 403)
        if self.path == "/api/info":
            SNAPSHOT["routes"] = scan()
            return self._json({"routes": [{"title": r["title"], "activities": [{"title": a["title"]} for a in r["activities"]],
                                           "paths": [{"title": p["title"]} for p in r["paths"]],
                                           "consists": [{"title": c["title"]} for c in r["consists"]]}
                                          for r in SNAPSHOT["routes"]],
                               "checks": setup_checks(), "options": current_options(), "roots": all_roots()})
        if self.path == "/api/status":
            return self._json(GAME.status())
        self._json({"error": "not found"}, 404)

    def do_POST(self):
        if not self._api_ok():
            return self._json({"error": "forbidden"}, 403)
        try:
            size = int(self.headers.get("Content-Length", 0))
            req = json.loads(self.rfile.read(min(size, 100000)) or "{}")
        except ValueError:
            return self._json({"error": "bad request"}, 400)
        if self.path == "/api/root":
            path = os.path.abspath(os.path.expanduser(str(req.get("path", "")).strip()))
            if not os.path.isdir(path) or not ci_child(path, "routes"):
                return self._json({"error": "That folder has no ROUTES folder inside it."})
            cfg = load_config()
            roots = [r for r in cfg.get("content_roots", []) if r != path]
            cfg["content_roots"] = [path] + roots
            save_config(cfg)
            return self._json({"ok": True})
        if self.path == "/api/start":
            args, error = build_args(req)
            if error:
                return self._json({"error": error})
            options = validated_options(req)
            changed = {k: v for k, v in options.items() if current_options().get(k) != v}
            if changed:
                try:
                    write_options(changed)
                except OSError as e:
                    return self._json({"error": "Could not save the display options: %s" % e})
            ok, result = GAME.start(args)
            if not ok:
                return self._json({"error": result})
            return self._json({"ok": True, "command": result if DRY_RUN else None, "changed": changed})
        self._json({"error": "not found"}, 404)


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def main():
    httpd = None
    for port in PORTS:
        try:
            httpd = Server(("127.0.0.1", port), Handler)
            break
        except OSError:
            continue
    if httpd is None:
        print("Could not open a local port (7788 to 7798 are all busy).")
        return 1
    url = "http://127.0.0.1:%d/" % httpd.server_address[1]
    print("Open Rails menu running at %s  (press Ctrl+C to quit)" % url, flush=True)
    if not os.environ.get("ORTS_NO_BROWSER"):
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
