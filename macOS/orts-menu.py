#!/usr/bin/env python3
"""
Open Rails for macOS: launcher menu.

The Windows Open Rails Menu.exe is built on Windows Forms and does not run on macOS. This is a
replacement that keeps its layout and behaviour: it serves a local web page that looks and works like
the Open Rails menu (installation profile, route, Activity or Explore with locomotive, consist and
path, time, season and weather, a details panel, Start), then starts the native macOS RunActivity build.

Run it with "Open Rails Menu.command" (double-click) or: python3 orts-menu.py
Needs only Python 3 (included with the Xcode Command Line Tools), no extra packages.
"""

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
# Reading MSTS / Open Rails content files (STF text format)
# --------------------------------------------------------------------------------------------

def read_stf(path):
    """Content files are text, usually UTF-16 with a byte order mark."""
    try:
        with open(path, "rb") as f:
            raw = f.read(400000)
    except OSError:
        return ""
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16", "ignore")
    if raw[:3] == b"\xef\xbb\xbf":
        raw = raw[3:]
    return raw.decode("utf-8", "ignore")


_KEYS = {}


def stf_str(text, key, start=0):
    """The value of the first `key ( ... )` in the text: quoted strings are joined ("a"+"b"), escapes handled."""
    rx = _KEYS.get(key)
    if rx is None:
        rx = _KEYS[key] = re.compile(r"(?<![\w])" + re.escape(key) + r"\s*\(", re.I)
    m = rx.search(text, start)
    if not m:
        return ""
    i, n, out = m.end(), len(text), []
    while i < n:
        c = text[i]
        if c == '"':
            j, buf = i + 1, []
            while j < n and text[j] != '"':
                if text[j] == "\\" and j + 1 < n:
                    buf.append("\n" if text[j + 1] == "n" else text[j + 1])
                    j += 2
                    continue
                buf.append(text[j])
                j += 1
            out.append("".join(buf))
            i = j + 1
        elif c in ")(":
            break
        elif c in " \t\r\n+":
            i += 1
        else:
            j = i
            while j < n and text[j] not in ' \t\r\n()"':
                j += 1
            out.append(text[i:j] + " ")
            i = j
    return "".join(out).strip()


def stf_ints(text, key, start=0):
    return [int(t) for t in stf_str(text, key, start).split() if t.lstrip("-").isdigit()]


_CACHE = {}


def cached(path, parser):
    """Parse a content file once; parse again only if the file changes."""
    try:
        key = (path, os.stat(path).st_mtime_ns)
    except OSError:
        return None
    if key not in _CACHE:
        _CACHE[key] = parser(path)
    return _CACHE[key]


def stem(path):
    return os.path.splitext(os.path.basename(path))[0]


def parse_path(path):
    t = read_stf(path)
    flags = stf_str(t, "TrPathFlags")
    try:
        flags = int(flags, 16) if flags else 0
    except ValueError:
        flags = 0
    name = stf_str(t, "Name") or stf_str(t, "TrPathName")
    unnamed = "<unnamed: %s>" % stem(path)
    return {"player": not (flags & 0x20), "name": name or unnamed,
            "start": stf_str(t, "TrPathStart") or unnamed, "end": stf_str(t, "TrPathEnd") or unnamed}


def parse_con(path):
    t = read_stf(path)
    engines = re.findall(r"EngineData\s*\(\s*([^\s)]+)\s+([^\s)]+)\s*\)", t, re.I)
    return {"name": stf_str(t, "Name") or "<unnamed: %s>" % stem(path), "engines": engines}


def parse_eng(path):
    t = read_stf(path)
    return {"name": stf_str(t, "Name"), "description": stf_str(t, "Description"),
            "cab": bool(re.search(r"CabView\s*\(\s*[^\s)]+", t, re.I))}


def parse_act(path):
    t = read_stf(path)
    i = t.lower().find("tr_activity_header")
    h = t[i:] if i >= 0 else t
    start, duration = stf_ints(h, "StartTime"), stf_ints(h, "Duration")
    difficulty, season, weather = stf_ints(h, "Difficulty"), stf_ints(h, "Season"), stf_ints(h, "Weather")
    return {"name": stf_str(h, "Name") or "<unnamed: %s>" % stem(path),
            "description": stf_str(h, "Description"), "briefing": stf_str(h, "Briefing"),
            "time": "%02d:%02d" % tuple(start[:2]) if len(start) >= 2 else "",
            "duration": "%d:%02d" % tuple(duration[:2]) if len(duration) >= 2 else "",
            "difficulty": difficulty[0] if difficulty else None,
            "season": season[0] if season else None, "weather": weather[0] if weather else None}


def route_info(route_dir, folder):
    """The route's display name and description, from its .trk file."""
    for trk in list_files(route_dir, ".trk")[:1]:
        t = read_stf(os.path.join(route_dir, trk))
        name = stf_str(t, "Name")
        if name:
            return name, stf_str(t, "Description")
    return clean(folder), ""


# --------------------------------------------------------------------------------------------
# Content folders ("installation profiles")
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


def scan_root(root):
    """Everything the menu shows for one content folder."""
    routes_dir = ci_child(root, "routes")
    trains_dir = ci_child(root, "trains")
    consists_dir = ci_child(trains_dir, "consists") if trains_dir else None
    trainset = ci_child(trains_dir, "trainset") if trains_dir else None

    # A consist belongs to the first of its engines that has a cab, like the Windows menu does.
    found = []
    for f in (list_files(consists_dir, ".con") if consists_dir else []):
        con = cached(os.path.join(consists_dir, f), parse_con)
        loco = None
        for eng_name, folder in (con or {"engines": []})["engines"]:
            eng_dir = ci_child(trainset, folder) if trainset else None
            eng_file = ci_child(eng_dir, eng_name + ".eng") if eng_dir else None
            eng = cached(eng_file, parse_eng) if eng_file else None
            if eng and eng["cab"]:
                loco = {"name": eng["name"] or "<unnamed: %s>" % eng_name, "description": eng["description"]}
                break
        if loco:
            found.append((con["name"], os.path.join(consists_dir, f), loco))
    locos = sorted({l["name"]: l for _, _, l in found}.values(), key=lambda l: l["name"].lower())
    loco_index = {l["name"]: i for i, l in enumerate(locos)}
    consists = [{"name": n, "file": f, "loco": loco_index[l["name"]]}
                for n, f, l in sorted(found, key=lambda c: c[0].lower())]

    routes = []
    for folder in sorted(os.listdir(routes_dir), key=lambda s: s.lower()):
        route_dir = os.path.join(routes_dir, folder)
        if not os.path.isdir(route_dir) or folder.startswith("."):
            continue
        paths_dir, acts_dir = ci_child(route_dir, "paths"), ci_child(route_dir, "activities")
        paths, acts = [], []
        for p in (list_files(paths_dir, ".pat") if paths_dir else []):
            info = cached(os.path.join(paths_dir, p), parse_path)
            if info and info["player"]:
                paths.append(dict(info, file=os.path.join(paths_dir, p)))
        for a in (list_files(acts_dir, ".act") if acts_dir else []):
            info = cached(os.path.join(acts_dir, a), parse_act)
            if info:
                acts.append(dict(info, file=os.path.join(acts_dir, a)))
        if not paths and not acts:
            continue  # not a playable route folder
        title, description = route_info(route_dir, folder)
        routes.append({"title": title, "description": description,
                       "paths": sorted(paths, key=lambda p: (p["start"].lower(), p["end"].lower())),
                       "activities": sorted(acts, key=lambda a: a["name"].lower())})
    routes.sort(key=lambda r: r["title"].lower())
    return {"name": os.path.basename(root.rstrip("/")) or root, "path": root,
            "locos": locos, "consists": consists, "routes": routes}


def scan():
    return [scan_root(r) for r in all_roots()]


def public_view(roots):
    """The scan without file paths: this is what the page gets."""
    def strip(items, drop="file"):
        return [{k: v for k, v in i.items() if k != drop} for i in items]
    return [{"name": r["name"], "path": r["path"], "locos": r["locos"], "consists": strip(r["consists"]),
             "routes": [{"title": t["title"], "description": t["description"], "paths": strip(t["paths"]),
                         "activities": strip(t["activities"])} for t in r["routes"]]} for r in roots]


# --------------------------------------------------------------------------------------------
# OpenRails.ini (the few display options this menu exposes)
# --------------------------------------------------------------------------------------------

OPTION_DEFAULTS = {"FullScreen": True, "Letterbox2DCab": False, "WindowSize": "1024x768", "ViewingDistance": 2000,
                   "Logging": True}


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
            elif kind == "int":
                try:
                    values[key] = int(payload.strip())
                except ValueError:
                    pass
    return values


def format_option(key, value):
    if key in ("FullScreen", "Letterbox2DCab", "Logging"):
        return "bool:true" if value else "bool:false"
    if key == "ViewingDistance":
        return "int:%d" % value
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
    for key in ("FullScreen", "Letterbox2DCab", "Logging"):
        if isinstance(req.get(key), bool):
            out[key] = req[key]
    distance = req.get("ViewingDistance")
    if isinstance(distance, int) and not isinstance(distance, bool) and 500 <= distance <= 5000:
        out["ViewingDistance"] = distance
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
         "fix": "No content found. Put it in ~/MSTS (folders ROUTES, TRAINS, GLOBAL), or press the Content button and add its folder."},
    ]


class Game(object):
    """Starts RunActivity. The game is not tied to this menu: its output goes to a file (not a pipe) and it
    runs in its own session, so closing the menu or the Terminal window does not close the game."""

    def __init__(self):
        self.proc = None
        self.log_path = os.path.join(HOME, "Library", "Logs", "Open Rails Menu", "last-run.txt")

    def running(self):
        return self.proc is not None and self.proc.poll() is None

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
        try:
            os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
            out = open(self.log_path, "w")
        except OSError:
            out = subprocess.DEVNULL
        self.proc = subprocess.Popen(cmd, cwd=PROGRAM_DIR, env=env, stdin=subprocess.DEVNULL, stdout=out,
                                     stderr=subprocess.STDOUT, start_new_session=True)
        if out is not subprocess.DEVNULL:
            out.close()  # the game keeps its own copy of the file
        return True, cmd

    def status(self):
        if self.proc is None:
            return {"state": "idle"}
        code = self.proc.poll()
        if code is None:
            return {"state": "running"}
        try:
            with open(self.log_path, "r", errors="replace") as f:
                tail = f.read()[-6000:].splitlines()[-25:]
        except OSError:
            tail = []
        return {"state": "exited", "code": code, "tail": tail}


GAME = Game()
SNAPSHOT = {"roots": []}
MANUAL_URL = "https://github.com/Aman1945/OPEN-RAIL-MAC/blob/master/macOS/USER-MANUAL.md"
OR_DOCS_URL = "https://open-rails.readthedocs.io/"

# Pictures from the Open Rails menu (the logo and the details-panel expander arrows).
LOGO_PNG = "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"
EXPANDER_OPEN_PNG = "iVBORw0KGgoAAAANSUhEUgAAAAkAAAAJCAYAAADgkQYQAAAABGdBTUEAALGPC/xhBQAAAAlwSFlzAAAOwgAADsIBFShKgAAAABp0RVh0U29mdHdhcmUAUGFpbnQuTkVUIHYzLjUuMTAw9HKhAAAAO0lEQVQoU4WKQQoAMAzC+v9PuyFYtCvsENBoAfjyCqrhotwqwnewg4jTHJaeQrjv4gehjWGODk/bkKAOXMC8RKTOOpAAAAAASUVORK5CYII="
EXPANDER_CLOSED_PNG = "iVBORw0KGgoAAAANSUhEUgAAAAkAAAAJCAYAAADgkQYQAAAABGdBTUEAALGPC/xhBQAAAAlwSFlzAAAOwQAADsEBuJFr7QAAABp0RVh0U29mdHdhcmUAUGFpbnQuTkVUIHYzLjUuMTAw9HKhAAAAP0lEQVQoU4WKAQoAMAgC+/+nXQqNrRwLrDwNAF9x8vqQYl4r/bNwPcltYQLruXpQ2lk9MqYgfhqBVhDrYAqxAOf8vETjHaK4AAAAAElFTkSuQmCC"


def local_manual():
    path = os.path.join(HERE, "USER MANUAL.html")
    return path if os.path.isfile(path) else None


def build_args(req):
    """Turn a menu selection into RunActivity arguments. Returns (args, error)."""
    try:
        root = SNAPSHOT["roots"][int(req["root"])]
        route = root["routes"][int(req["route"])]
        if req.get("mode") == "activity":
            return ["-start", "-activity", route["activities"][int(req["activity"])]["file"]], None
        time_value = str(req.get("time", "12:00:00")).strip()
        season, weather = str(req.get("season", "1")), str(req.get("weather", "0"))
        if not re.match(r"^\d{1,2}:\d{2}(:\d{2})?$", time_value) or season not in ("0", "1", "2", "3") \
                or weather not in ("0", "1", "2"):
            return None, "Please enter the time as hours and minutes, for example 12:00."
        if time_value.count(":") == 1:  # the menu gives HH:MM
            time_value += ":00"
        return ["-start", "-explorer", route["paths"][int(req["path"])]["file"],
                root["consists"][int(req["consist"])]["file"], time_value, season, weather], None
    except (KeyError, IndexError, ValueError, TypeError):
        return None, "Please choose a route, and a consist and path (or an activity)."


def open_target(what):
    """Tools menu: show the log file or edit OpenRails.ini in the default app. Returns (error, command)."""
    if what == "log":
        target, cmd = os.path.join(HOME, "Desktop", "OpenRailsLog.txt"), None
        error = "There is no log file yet. Start the game first."
    elif what == "ini":
        target, cmd = INI_PATH, None
        error = "OpenRails.ini was not found."
    else:
        return "Unknown item.", None
    if not os.path.isfile(target):
        return error, None
    cmd = ["open", "-t", target] if what == "ini" else ["open", target]
    if not DRY_RUN:
        subprocess.Popen(cmd)
    return None, cmd


# --------------------------------------------------------------------------------------------
# Web page: the Open Rails menu (854 x 548 client area, controls at the same positions)
# --------------------------------------------------------------------------------------------

PAGE = r"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Open Rails</title>
<link rel="icon" href="data:image/png;base64,__LOGO__">
<style>
  :root { --face:#F0F0F0; --btn:#E1E1E1; --btnb:#ADADAD; --hot:#E5F1FB; --hotb:#0078D7; --down:#CCE4F7; --downb:#005499;
          --offb:#BFBFBF; --offt:#838383; --line:#DCDCDC; }
  * { box-sizing:border-box; }
  html { background:#CBD1DA; }
  body { margin:0; min-height:100vh; display:flex; justify-content:center; align-items:flex-start; padding:28px 12px;
         font:11px/13px Tahoma,"Segoe UI",Arial,sans-serif; color:#000; }
  html.native { background:var(--face); }
  .native body { padding:0; display:block; min-height:0; }
  .native #win { border:0; box-shadow:none; width:854px; }
  .native #title { display:none; }
  #win { width:856px; background:var(--face); border:1px solid #7A8AA0; box-shadow:0 12px 36px rgba(0,0,0,.35); }
  #title { height:31px; background:#fff; display:flex; align-items:center; padding:0 9px; font:12px "Segoe UI",system-ui,sans-serif; }
  #title img { width:16px; height:16px; margin-right:8px; }
  #form { position:relative; width:854px; height:548px; background:var(--face); user-select:none; -webkit-user-select:none; }
  .a { position:absolute; }
  label.a { white-space:nowrap; }
  /* combo boxes (drop-down lists look like flat buttons on Windows 10) */
  select, .cb { position:absolute; height:21px; font:inherit; color:#000; background-color:var(--btn); border:1px solid var(--btnb);
         border-radius:0; padding:0 18px 0 3px; margin:0; appearance:none; -webkit-appearance:none; outline:none;
         background-image:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='9' height='5'><path d='M0 0h9L4.5 5z' fill='%23444'/></svg>");
         background-repeat:no-repeat; background-position:right 5px center; cursor:default; }
  select:hover:not(:disabled) { background-color:var(--hot); border-color:var(--hotb); }
  select:focus { border-color:var(--hotb); }
  select:disabled { background-color:var(--face); border-color:var(--offb); color:var(--offt); background-image:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='9' height='5'><path d='M0 0h9L4.5 5z' fill='%23A0A0A0'/></svg>"); }
  input[type=text] { position:absolute; height:21px; font:inherit; color:#000; background:#fff; border:1px solid var(--btnb); padding:0 3px; margin:0; outline:none; user-select:text; -webkit-user-select:text; }
  input[type=text]:focus { border-color:var(--hotb); }
  input[type=text]:disabled { background:var(--face); border-color:var(--offb); color:var(--offt); }
  /* buttons */
  .btn { position:absolute; font:inherit; color:#000; background:var(--btn); border:1px solid var(--btnb); border-radius:0; padding:0; cursor:default; outline:none; }
  .btn:hover:not(:disabled) { background:var(--hot); border-color:var(--hotb); }
  .btn:active:not(:disabled) { background:var(--down); border-color:var(--downb); }
  .btn:disabled { background:var(--face); border-color:var(--offb); color:var(--offt); }
  .btn.def { border-color:var(--hotb); box-shadow:inset 0 0 0 1px var(--hotb); }
  /* group boxes */
  .gb { position:absolute; }
  .gb::before { content:""; position:absolute; left:0; right:0; top:7px; bottom:0; border:1px solid var(--line); border-radius:2px; }
  .gb > .t { position:absolute; left:6px; top:0; background:var(--face); padding:0 2px; }
  .gb.off > .t, .off { color:var(--offt); }
  .rad, .chk { display:flex; align-items:center; gap:4px; }
  .rad input, .chk input { margin:0; width:13px; height:13px; accent-color:#0078D7; }
  /* details panel */
  #details { position:absolute; left:299px; top:31px; width:543px; height:379px; background:#fff; border:1px solid #7A7A7A;
             overflow-y:auto; overflow-x:hidden; user-select:text; -webkit-user-select:text; }
  .dt { position:relative; margin:2px; padding-right:19px; min-height:17px; line-height:17px; font-weight:bold; }
  .dt.bad { color:#C00000; }
  .dx { position:absolute; right:0; top:0; width:17px; height:17px; border:0; padding:0; background:transparent center no-repeat; }
  .ds { margin:2px; white-space:pre-wrap; display:-webkit-box; -webkit-box-orient:vertical; -webkit-line-clamp:5; overflow:hidden; }
  .ds.open { display:block; }
  /* the picture next to "Open Rails" and the status line */
  #logo { position:absolute; left:12px; top:472px; width:64px; height:64px; }
  #brand { position:absolute; left:96px; top:472px; width:224px; height:64px; display:flex; align-items:center; font:bold 18pt Arial,Helvetica,sans-serif; }
  #status { position:absolute; left:330px; top:536px; height:12px; line-height:12px; color:#555; font-size:10px; }
  /* dialogs and menus */
  #ov { position:fixed; inset:0; background:rgba(0,0,0,.28); display:none; align-items:center; justify-content:center; z-index:20; }
  .dlg { background:var(--face); border:1px solid #6E7E96; box-shadow:0 10px 30px rgba(0,0,0,.4); min-width:380px; max-width:620px; }
  .dlg .tb { height:30px; background:#fff; display:flex; align-items:center; padding:0 10px; font:12px "Segoe UI",system-ui,sans-serif; }
  .dlg .bd { padding:14px 16px; position:relative; }
  .dlg .ft { padding:10px 14px 14px; text-align:right; }
  .dlg .ft .btn { position:static; width:75px; height:23px; margin-left:6px; }
  .dlg pre { margin:10px 0 0; max-height:170px; overflow:auto; background:#fff; border:1px solid var(--btnb); padding:6px; font:10px/12px Menlo,monospace; white-space:pre-wrap; user-select:text; }
  .dlg .row { display:flex; align-items:center; gap:8px; margin:6px 0; }
  .dlg input[type=text], .dlg select { position:static; }
  .dlg select { width:220px; }
  .pop { position:absolute; background:#F2F2F2; border:1px solid #CCC; box-shadow:2px 2px 4px rgba(0,0,0,.25); padding:2px; z-index:10; }
  .pi { padding:4px 24px; white-space:nowrap; }
  .pi:hover { background:#91C9F7; }
  .list { background:#fff; border:1px solid var(--btnb); padding:2px; margin:4px 0 10px; max-height:130px; overflow:auto; user-select:text; }
  .list div { padding:2px 4px; }
</style></head>
<body>
<div id="win">
  <div id="title"><img src="data:image/png;base64,__LOGO__" alt="">Open Rails</div>
  <div id="form">
    <label class="a" style="left:12px;top:12px">Installation profile:</label>
    <select id="profile" style="left:12px;top:31px;width:281px"></select>
    <label class="a" style="left:12px;top:58px">Route:</label>
    <select id="route" style="left:12px;top:77px;width:281px"></select>
    <label class="a" style="left:12px;top:104px">Mode:</label>
    <label class="a rad" style="left:12px;top:124px;width:130px;height:20px"><input type="radio" name="mode" checked>Activity</label>
    <label class="a rad off" style="left:163px;top:123px;width:130px;height:20px" title="Timetable mode is not available on macOS yet"><input type="radio" name="mode" disabled>Timetable</label>

    <div class="a" style="left:9px;top:146px;width:287px;height:311px">
      <label class="a" style="left:3px;top:3px">Activity:</label>
      <select id="activity" style="left:3px;top:22px;width:281px"></select>
      <label class="a" style="left:3px;top:49px">Locomotive:</label>
      <select id="loco" style="left:3px;top:68px;width:281px"></select>
      <label class="a" style="left:3px;top:93px">Consist:</label>
      <select id="consist" style="left:3px;top:112px;width:281px"></select>
      <label class="a" style="left:3px;top:139px">Starting at:</label>
      <select id="startat" style="left:3px;top:158px;width:281px"></select>
      <label class="a" style="left:3px;top:185px">Heading to:</label>
      <select id="headto" style="left:3px;top:204px;width:281px"></select>
      <label class="a" style="left:4px;top:234px">Time:</label>
      <input type="text" id="time" list="times" value="12:00" style="left:61px;top:231px;width:73px" spellcheck="false">
      <datalist id="times"></datalist>
      <label class="a" style="left:143px;top:234px">Duration:</label>
      <select id="duration" style="left:211px;top:231px;width:73px" disabled></select>
      <label class="a" style="left:4px;top:262px">Season:</label>
      <select id="season" style="left:61px;top:259px;width:73px"></select>
      <label class="a" style="left:143px;top:262px">Difficulty:</label>
      <select id="difficulty" style="left:211px;top:259px;width:73px" disabled></select>
      <label class="a" style="left:4px;top:289px">Weather:</label>
      <select id="weather" style="left:61px;top:286px;width:73px"></select>
    </div>

    <div id="details"></div>

    <div class="a" style="left:311px;top:416px;width:187px;height:120px">
      <button class="btn" id="bContent" style="left:3px;top:19px;width:100px;height:23px">Content</button>
      <button class="btn" id="bTools" style="left:3px;top:48px;width:100px;height:23px">Tools &#9660;</button>
      <button class="btn" id="bDocs" style="left:3px;top:79px;width:100px;height:23px">Documents &#9660;</button>
      <button class="btn" id="bOptions" style="left:109px;top:19px;width:75px;height:23px">Options</button>
      <label class="a chk" style="left:109px;top:48px;width:70px;height:17px"><input type="checkbox" id="logging">Logging</label>
    </div>

    <div class="gb" style="left:504px;top:416px;width:87px;height:120px"><span class="t">Singleplayer</span>
      <button class="btn def" id="start" style="left:6px;top:19px;width:75px;height:46px">Start</button>
      <button class="btn" style="left:7px;top:79px;width:75px;height:41px;line-height:13px" disabled title="Resuming a saved game is not available in this menu yet">Resume/<br>Replay...</button>
    </div>

    <div class="gb off" style="left:597px;top:416px;width:245px;height:120px" title="Multiplayer is not available on macOS yet"><span class="t">Multiplayer</span>
      <label class="a" style="left:6px;top:22px">User name:</label><input type="text" style="left:83px;top:19px;width:156px" disabled>
      <label class="a" style="left:6px;top:48px">Host/port:</label><input type="text" style="left:83px;top:45px;width:156px" disabled>
      <label class="a rad off" style="left:9px;top:67px;width:75px;height:20px"><input type="radio" name="mp" disabled>Client</label>
      <label class="a rad off" style="left:9px;top:91px;width:75px;height:20px"><input type="radio" name="mp" disabled>Server</label>
      <button class="btn" style="left:83px;top:88px;width:75px;height:23px" disabled>Start MP</button>
      <button class="btn" style="left:164px;top:88px;width:75px;height:23px" disabled>Resume MP</button>
    </div>

    <img id="logo" src="data:image/png;base64,__LOGO__" alt="">
    <div id="brand">Open Rails</div>
    <div id="status"></div>
  </div>
</div>
<div id="ov"></div>
<script>
const TOKEN = "__TOKEN__";
const $ = id => document.getElementById(id);
const SEASONS = ["Spring", "Summer", "Autumn", "Winter"], WEATHERS = ["Clear", "Snow", "Rain"], DIFFS = ["Easy", "Medium", "Hard"];
const EXP_OPEN = "data:image/png;base64,__EXPOPEN__", EXP_CLOSED = "data:image/png;base64,__EXPCLOSED__";
let INFO = null, RUNNING = false;

async function api(path, body) {
  const r = await fetch(path, {method: body ? 'POST' : 'GET', headers: {'X-ORTS-Token': TOKEN, 'Content-Type': 'application/json'},
                               body: body ? JSON.stringify(body) : undefined});
  return r.json();
}
function fill(sel, items) {
  sel.textContent = '';
  items.forEach(it => { const o = document.createElement('option'); o.value = it.value; o.textContent = it.label; sel.appendChild(o); });
}
const root = () => INFO && INFO.roots[+$('profile').value];
const route = () => { const r = root(); return r && r.routes[+$('route').value]; };
const isExplore = () => { const t = route(); return !!t && t.paths.length > 0 && $('activity').value === 'explore'; };
const activityNow = () => { const t = route(); const v = $('activity').value; return (t && /^a\d+$/.test(v)) ? t.activities[+v.slice(1)] : null; };

function onProfile() { const r = root(); fill($('route'), r ? r.routes.map((t, i) => ({label: t.title, value: i})) : []); onRoute(); }
function onRoute() {
  const t = route(), items = [];
  if (t && t.paths.length) items.push({label: '- Explore Route -', value: 'explore'});
  if (t) t.activities.forEach((a, i) => items.push({label: a.name, value: 'a' + i}));
  fill($('activity'), items); onActivity();
}
function onActivity() {
  const t = route(), r = root(), ex = isExplore(), act = activityNow();
  fill($('loco'), ex ? [{label: '- Any Locomotive -', value: -1}].concat(r.locos.map((l, i) => ({label: l.name, value: i}))) : []);
  const starts = ex ? [...new Set(t.paths.map(p => p.start))] : [];
  fill($('startat'), starts.map(s => ({label: s, value: s})));
  onLoco(true); onStartAt(true);
  // season, weather, time: shown for an activity, chosen for Explore
  if (act) {
    $('time').value = act.time || '';
    if (act.season !== null) $('season').selectedIndex = act.season;
    if (act.weather !== null) $('weather').selectedIndex = act.weather;
  }
  fill($('duration'), act && act.duration ? [{label: act.duration, value: 0}] : []);
  fill($('difficulty'), act && act.difficulty !== null ? [{label: DIFFS[act.difficulty] || '', value: 0}] : []);
  update();
}
function onLoco(quiet) {
  const r = root(), li = +$('loco').value, ex = isExplore();
  fill($('consist'), !ex ? [] : r.consists.map((c, i) => ({c, i})).filter(x => li < 0 || x.c.loco === li).map(x => ({label: x.c.name, value: x.i})));
  if (!quiet) update();
}
function onStartAt(quiet) {
  const t = route(), s = $('startat').value, ex = isExplore();
  fill($('headto'), !ex ? [] : t.paths.map((p, i) => ({p, i})).filter(x => x.p.start === s).map(x => ({label: x.p.end, value: x.i})));
  if (!quiet) update();
}

function update() {
  const ex = isExplore(), act = activityNow(), t = route();
  for (const id of ['loco', 'consist', 'startat', 'headto']) $(id).disabled = !ex || !$(id).options.length;
  $('time').disabled = !ex; $('season').disabled = !ex; $('weather').disabled = !ex;
  $('route').disabled = !$('route').options.length; $('activity').disabled = !$('activity').options.length;
  $('start').disabled = RUNNING || !(ex ? $('consist').value !== '' && $('headto').value !== '' : !!act);
  showDetails();
}

function section(title, text, bad) {
  const box = $('details');
  const dt = document.createElement('div'); dt.className = 'dt' + (bad ? ' bad' : ''); dt.textContent = title;
  const ds = document.createElement('div'); ds.className = 'ds' + (bad ? ' open' : ''); ds.textContent = text;
  box.appendChild(dt); box.appendChild(ds);
  if (!bad && ds.scrollHeight > ds.clientHeight + 1) {
    const x = document.createElement('button'); x.className = 'dx'; x.style.backgroundImage = 'url(' + EXP_CLOSED + ')';
    x.onclick = () => { const open = ds.classList.toggle('open'); x.style.backgroundImage = 'url(' + (open ? EXP_OPEN : EXP_CLOSED) + ')'; };
    dt.appendChild(x);
  }
}
function showDetails() {
  $('details').textContent = '';
  const bad = (INFO ? INFO.checks : []).filter(c => !c.ok);
  if (bad.length) section('Setup problem', bad.map(c => c.label + ': ' + c.fix).join('\n\n'), true);
  const t = route(), r = root(), act = activityNow();
  if (t && t.description) section('Route: ' + t.title, t.description);
  if (isExplore()) {
    const c = r.consists[+$('consist').value], l = c && r.locos[c.loco];
    if (l && l.description) section('Locomotive: ' + l.name, l.description);
    const p = t.paths[+$('headto').value];
    if (p) section('Path: ' + p.name, 'Starting at: ' + p.start + '\nHeading to: ' + p.end);
  } else if (act && act.description) {
    section('Activity: ' + act.name, act.description);
    if (act.briefing) section('Activity Briefing', act.briefing);
  }
}

/* ---- dialogs, menus --------------------------------------------------------------------------- */
function dialog(title, body, buttons) {
  const ov = $('ov'); ov.textContent = ''; ov.style.display = 'flex';
  const d = document.createElement('div'); d.className = 'dlg';
  const tb = document.createElement('div'); tb.className = 'tb'; tb.textContent = title;
  const bd = document.createElement('div'); bd.className = 'bd'; bd.appendChild(body);
  const ft = document.createElement('div'); ft.className = 'ft';
  const close = () => { ov.style.display = 'none'; ov.textContent = ''; };
  buttons.forEach(b => {
    const x = document.createElement('button'); x.className = 'btn' + (b.def ? ' def' : ''); x.textContent = b.label;
    x.onclick = async () => { if (!b.action || (await b.action()) !== false) close(); }; ft.appendChild(x);
  });
  d.appendChild(tb); d.appendChild(bd); d.appendChild(ft); ov.appendChild(d);
  return close;
}
function msg(text, tail) {
  const b = document.createElement('div'); const p = document.createElement('div'); p.textContent = text; b.appendChild(p);
  if (tail && tail.length) { const pre = document.createElement('pre'); pre.textContent = tail.join('\n'); b.appendChild(pre); }
  dialog('Open Rails', b, [{label: 'OK', def: true}]);
}
function popup(button, items) {
  document.querySelectorAll('.pop').forEach(p => p.remove());
  const pop = document.createElement('div'); pop.className = 'pop';
  items.forEach(it => { const d = document.createElement('div'); d.className = 'pi'; d.textContent = it.label; d.onclick = () => { pop.remove(); it.action(); }; pop.appendChild(d); });
  button.parentElement.appendChild(pop);
  pop.style.left = button.offsetLeft + 'px'; pop.style.top = (button.offsetTop - pop.offsetHeight - 2) + 'px';
  setTimeout(() => document.addEventListener('click', () => pop.remove(), {once: true}), 0);
}
function row(label, control) {
  const r = document.createElement('div'); r.className = 'row'; const l = document.createElement('span'); l.textContent = label;
  if (label) r.appendChild(l); r.appendChild(control); return r;
}
function checkbox(text, checked) {
  const l = document.createElement('label'); l.className = 'chk'; const i = document.createElement('input'); i.type = 'checkbox'; i.checked = checked;
  l.appendChild(i); l.appendChild(document.createTextNode(text)); return [l, i];
}

function openOptions() {
  const o = INFO.options, body = document.createElement('div');
  const [l1, fs] = checkbox('Full screen', o.FullScreen), [l2, lb] = checkbox('Show the whole 2D cab (black bars instead of cropping)', o.Letterbox2DCab);
  const ws = document.createElement('input'); ws.type = 'text'; ws.value = o.WindowSize; ws.style.width = '90px';
  const vd = document.createElement('select');
  const dists = [[750, 'Fast: 750 m'], [1000, 'Balanced: 1000 m'], [1500, 'Detailed: 1500 m'], [2000, 'Far: 2000 m (Open Rails default)']];
  if (!dists.some(d => d[0] === o.ViewingDistance)) dists.push([o.ViewingDistance, 'Custom: ' + o.ViewingDistance + ' m']);
  dists.forEach(d => { const op = document.createElement('option'); op.value = d[0]; op.textContent = d[1]; vd.appendChild(op); }); vd.value = o.ViewingDistance;
  const hint = document.createElement('div'); hint.style.cssText = 'color:#555;margin:2px 0 8px;max-width:440px';
  hint.textContent = 'A longer viewing distance draws many more objects, which can lower the frame rate, especially when you look back along the train. If the game is choppy, choose a shorter distance.';
  body.appendChild(l1); body.appendChild(l2); body.appendChild(row('Window size (when not full screen):', ws));
  body.appendChild(row('Viewing distance:', vd)); body.appendChild(hint);
  dialog('Options', body, [
    {label: 'OK', def: true, action: async () => {
      const opts = {FullScreen: fs.checked, Letterbox2DCab: lb.checked, WindowSize: ws.value.trim(), ViewingDistance: +vd.value};
      const res = await api('/api/options', opts);
      if (res.error) { msg(res.error); return false; }
      Object.assign(INFO.options, opts);
    }},
    {label: 'Cancel'}]);
}
function openContent() {
  const body = document.createElement('div');
  const p = document.createElement('div'); p.textContent = 'Installation profiles (folders that contain ROUTES, TRAINS and GLOBAL):'; body.appendChild(p);
  const list = document.createElement('div'); list.className = 'list';
  (INFO.roots.length ? INFO.roots : [{name: '(none found yet)', path: ''}]).forEach(r => { const d = document.createElement('div'); d.textContent = r.path ? r.name + '   –   ' + r.path : r.name; list.appendChild(d); });
  body.appendChild(list);
  const inp = document.createElement('input'); inp.type = 'text'; inp.style.width = '330px'; inp.placeholder = '/Users/you/MSTS';
  const add = document.createElement('button'); add.className = 'btn'; add.textContent = 'Add'; add.style.cssText = 'position:static;width:75px;height:23px';
  const err = document.createElement('div'); err.style.cssText = 'color:#C00000;margin-top:4px;min-height:13px';
  add.onclick = async () => { const res = await api('/api/root', {path: inp.value}); if (res.error) { err.textContent = res.error; return; } $('ov').style.display = 'none'; await load(); };
  const r = row('Add a folder:', inp); r.appendChild(add); body.appendChild(r); body.appendChild(err);
  dialog('Content', body, [{label: 'Close', def: true}]);
}

/* ---- start, status ---------------------------------------------------------------------------- */
async function startGame() {
  const t = route(); if (!t) return;
  const ex = isExplore(), body = {root: +$('profile').value, route: +$('route').value, mode: ex ? 'explore' : 'activity'};
  if (ex) Object.assign(body, {consist: +$('consist').value, path: +$('headto').value, time: $('time').value.trim(), season: $('season').value, weather: $('weather').value});
  else body.activity = +$('activity').value.slice(1);
  const res = await api('/api/start', body);
  if (res.error) { msg(res.error); return; }
  saveSelection();
  RUNNING = true; $('status').textContent = 'Open Rails is running. A game window opens; loading can take a few minutes.'; update(); poll();
}
async function poll() {
  const s = await api('/api/status');
  if (s.state === 'running') { setTimeout(poll, 2000); return; }
  RUNNING = false; $('status').textContent = ''; update();
  if (s.state === 'exited' && s.code !== 0) msg('Open Rails stopped with an error (code ' + s.code + '). See OpenRailsLog.txt on your Desktop.', s.tail);
}

/* ---- remember the last choices (like the Windows menu) ---------------------------------------- */
function saveSelection() {
  try {
    const text = id => { const o = $(id).selectedOptions[0]; return o ? o.textContent : ''; };
    localStorage.setItem('ortsMenu', JSON.stringify({profile: root().path, route: text('route'), activity: text('activity'), loco: text('loco'), consist: text('consist'),
      startat: text('startat'), headto: text('headto'), time: $('time').value, season: $('season').value, weather: $('weather').value}));
  } catch (e) {}
}
function restoreSelection() {
  let s; try { s = JSON.parse(localStorage.getItem('ortsMenu') || 'null'); } catch (e) {}
  if (!s) return;
  const pick = (id, label) => { const i = [...$(id).options].findIndex(o => o.textContent === label); if (i >= 0) $(id).selectedIndex = i; };
  const pi = INFO.roots.findIndex(r => r.path === s.profile); if (pi >= 0) { $('profile').value = pi; onProfile(); }
  pick('route', s.route); onRoute(); pick('activity', s.activity); onActivity();
  if (isExplore()) { pick('loco', s.loco); onLoco(true); pick('consist', s.consist); pick('startat', s.startat); onStartAt(true); pick('headto', s.headto);
    if (s.time) $('time').value = s.time; $('season').value = s.season; $('weather').value = s.weather; }
  update();
}

async function load() {
  INFO = await api('/api/info');
  fill($('profile'), INFO.roots.map((r, i) => ({label: r.name, value: i})));
  $('profile').disabled = !INFO.roots.length;
  $('logging').checked = INFO.options.Logging;
  onProfile(); restoreSelection();
}
document.addEventListener('DOMContentLoaded', () => {
  if (/[?&]app=1/.test(location.search)) {   // inside the Mac app: look like a window, not a web page
    document.documentElement.classList.add('native');
    document.addEventListener('contextmenu', e => { if (e.target.tagName !== 'INPUT') e.preventDefault(); });
  }
  fill($('season'), SEASONS.map((s, i) => ({label: s, value: i}))); $('season').selectedIndex = 1;
  fill($('weather'), WEATHERS.map((s, i) => ({label: s, value: i})));
  $('times').innerHTML = Array.from({length: 24}, (_, h) => '<option value="' + String(h).padStart(2, '0') + ':00">').join('');
  $('profile').onchange = onProfile; $('route').onchange = onRoute; $('activity').onchange = onActivity;
  $('loco').onchange = () => onLoco(); $('startat').onchange = () => onStartAt(); $('consist').onchange = update; $('headto').onchange = update;
  $('start').onclick = startGame; $('bOptions').onclick = openOptions; $('bContent').onclick = openContent;
  $('logging').onchange = async e => { await api('/api/options', {Logging: e.target.checked}); INFO.options.Logging = e.target.checked; };
  $('bTools').onclick = e => popup(e.target, [
    {label: 'Show the log file', action: async () => { const r = await api('/api/open', {what: 'log'}); if (r.error) msg(r.error); }},
    {label: 'Edit OpenRails.ini', action: async () => { const r = await api('/api/open', {what: 'ini'}); if (r.error) msg(r.error); }}]);
  $('bDocs').onclick = e => popup(e.target, [
    {label: 'macOS user manual', action: () => window.open('/manual', '_blank')},
    {label: 'Open Rails manual (website)', action: () => window.open('__ORDOCS__', '_blank', 'noopener')}]);
  load();
});
</script></body></html>"""


# --------------------------------------------------------------------------------------------
# HTTP server (local only; every API call needs the per-run token)
# --------------------------------------------------------------------------------------------

class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json", extra=None):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
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
        route = urllib.parse.urlsplit(self.path).path
        if route in ("/", "/index.html"):
            page = (PAGE.replace("__TOKEN__", TOKEN).replace("__LOGO__", LOGO_PNG).replace("__EXPOPEN__", EXPANDER_OPEN_PNG)
                    .replace("__EXPCLOSED__", EXPANDER_CLOSED_PNG).replace("__ORDOCS__", OR_DOCS_URL))
            return self._send(200, page, "text/html")
        if route == "/manual":
            local = local_manual()
            if local:
                with open(local, "rb") as f:
                    return self._send(200, f.read(), "text/html")
            return self._send(302, "", "text/plain", {"Location": MANUAL_URL})
        if not self._api_ok():
            return self._json({"error": "forbidden"}, 403)
        if route == "/api/info":
            SNAPSHOT["roots"] = scan()
            return self._json({"roots": public_view(SNAPSHOT["roots"]), "checks": setup_checks(), "options": current_options()})
        if route == "/api/status":
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
            cfg["content_roots"] = [path] + [r for r in cfg.get("content_roots", []) if r != path]
            save_config(cfg)
            return self._json({"ok": True})
        if self.path == "/api/options":
            options = validated_options(req)
            if "WindowSize" in req and "WindowSize" not in options:
                return self._json({"error": "Please enter the window size like 1280x720."})
            changed = {k: v for k, v in options.items() if current_options().get(k) != v}
            try:
                if changed:
                    write_options(changed)
            except OSError as e:
                return self._json({"error": "Could not save the options: %s" % e})
            return self._json({"ok": True, "changed": changed})
        if self.path == "/api/open":
            error, cmd = open_target(req.get("what"))
            return self._json({"error": error} if error else {"ok": True, "command": cmd if DRY_RUN else None})
        if self.path == "/api/start":
            args, error = build_args(req)
            if error:
                return self._json({"error": error})
            options = validated_options(req)  # still accepted here, for scripts
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
