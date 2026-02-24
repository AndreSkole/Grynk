"""Grynk gx built-in object — always available, zero imports."""

import os
import sys

# Ensure UTF-8 output on Windows so box-drawing/unicode chars work
if sys.platform == 'win32':
    try:
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        if hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

import math
import json
import time
import uuid
import hashlib
import hmac as _hmac
import base64
import random
import re
import platform as _platform
import subprocess
import threading
import shutil
from datetime import datetime

from .types import (
    GrynkString, GrynkList, GrynkDict, GrynkNum, GrynkResponse,
    wrap, unwrap, grynk_str, grynk_bool
)
from .errors import GrynkRuntimeError


# ── lazy optional imports ──────────────────────────────────────────────────────

def _try_import(name):
    try:
        import importlib
        return importlib.import_module(name)
    except ImportError:
        return None


# ── color helpers ─────────────────────────────────────────────────────────────

try:
    from colorama import Fore, Back, Style, init as _cinit
    _cinit(autoreset=True)
    _HAS_COLOR = True
except ImportError:
    _HAS_COLOR = False

_COLOR_MAP = {
    'red':     '\033[31m',
    'green':   '\033[32m',
    'yellow':  '\033[33m',
    'blue':    '\033[34m',
    'magenta': '\033[35m',
    'cyan':    '\033[36m',
    'white':   '\033[37m',
    'bold':    '\033[1m',
    'reset':   '\033[0m',
}

def _colorize(color, text):
    if not _HAS_COLOR:
        return text
    code = _COLOR_MAP.get(str(color).lower(), '')
    reset = _COLOR_MAP['reset']
    return f"{code}{text}{reset}"


# ── HTTP helpers ──────────────────────────────────────────────────────────────

def _build_response(r):
    try:
        j = r.json()
    except Exception:
        j = None
    return GrynkResponse(r.text, r.status_code, r.ok, j)


# ── AI stubs (rule-based fallback when openai not installed) ──────────────────

def _ai_fallback(prompt):
    prompt = unwrap(prompt).strip()
    return GrynkString(f"[AI response to: {prompt[:80]}]")

def _ai_sentiment(text):
    t = unwrap(text).lower()
    pos = ['good','great','happy','love','excellent','awesome','wonderful','fantastic','nice','best']
    neg = ['bad','terrible','hate','awful','horrible','worst','ugly','sad','poor']
    score = sum(1 for w in pos if w in t) - sum(1 for w in neg if w in t)
    if score > 0: return GrynkString('positive')
    if score < 0: return GrynkString('negative')
    return GrynkString('neutral')

def _ai_summarize(text, n=3):
    sentences = re.split(r'(?<=[.!?])\s+', unwrap(text))
    return GrynkString(' '.join(sentences[:unwrap(n)]) if sentences else '')

def _ai_translate(text, lang):
    return GrynkString(f"[{unwrap(lang).upper()}]: {unwrap(text)}")

def _ai_classify(text, labels):
    ls = [unwrap(l) for l in (labels.data if isinstance(labels, GrynkList) else list(labels))]
    t = unwrap(text).lower()
    for l in ls:
        if l.lower() in t:
            return GrynkString(l)
    return GrynkString(ls[0] if ls else 'unknown')

def _ai_code(description, language='python'):
    return GrynkString(f"# {unwrap(language)}\n# TODO: {unwrap(description)}\npass")


# ── gx class ──────────────────────────────────────────────────────────────────

# Singleton state
_GX_INSTANCE = None

# ── GxGUI wrapper ─────────────────────────────────────────────────────────────

class GxGUI:
    def __init__(self, root):
        self.root = root
        self.widgets = []
        self._ctk = _try_import('customtkinter')

    def add_button(self, text, callback, row=None):
        target = self._get_target(row)
        if self._ctk:
            btn = self._ctk.CTkButton(target, text=unwrap(text), command=lambda: self._trigger(callback), width=60)
        else:
            import tkinter as tk
            btn = tk.Button(target, text=unwrap(text), command=lambda: self._trigger(callback))
        btn.pack(side="left" if row is not None else "top", pady=5, padx=5)
        self.widgets.append(btn)
        return btn

    def add_label(self, text, row=None):
        target = self._get_target(row)
        if self._ctk:
            lbl = self._ctk.CTkLabel(target, text=unwrap(text))
        else:
            import tkinter as tk
            lbl = tk.Label(target, text=unwrap(text))
        lbl.pack(side="left" if row is not None else "top", pady=5, padx=5)
        self.widgets.append(lbl)
        return GxGUIWidget(lbl)

    def add_entry(self, placeholder="", row=None):
        target = self._get_target(row)
        if self._ctk:
            entry = self._ctk.CTkEntry(target, placeholder_text=unwrap(placeholder))
        else:
            import tkinter as tk
            entry = tk.Entry(target)
        entry.pack(side="left" if row is not None else "top", fill="x" if row is None else "none", expand=True, pady=5, padx=5)
        self.widgets.append(entry)
        return GxGUIWidget(entry)

    def _get_target(self, row_id):
        if row_id is None:
            return self.root
        
        # Lazy check/create row frame
        attr_name = f"_row_frame_{row_id}"
        if not hasattr(self, attr_name):
            if self._ctk:
                frame = self._ctk.CTkFrame(self.root, fg_color="transparent")
            else:
                import tkinter as tk
                frame = tk.Frame(self.root)
            frame.pack(fill="x", padx=10)
            setattr(self, attr_name, frame)
        
        return getattr(self, attr_name)

    def run(self):
        self.root.mainloop()

    def _trigger(self, fn):
        from .types import _call_fn
        try:
            _call_fn(fn, [])
        except Exception as e:
            print(f"GUI Callback Error: {e}")

class GxGUIWidget:
    def __init__(self, widget):
        self.widget = widget
    
    def get_attr(self, name):
        if name == "text":
            if hasattr(self.widget, 'get'): return GrynkString(self.widget.get())
            if hasattr(self.widget, 'cget'): return GrynkString(self.widget.cget("text"))
            return GrynkString("")
        
        methods = {
            "set": self._set_text,
            "clear": self._clear,
            "focus": lambda: (self.widget.focus(), None)[1]
        }
        if name in methods: return methods[name]
        raise GrynkRuntimeError(f"Widget has no attribute '{name}'")

    def _set_text(self, text):
        t = unwrap(text)
        if hasattr(self.widget, 'configure'):
            if 'text' in self.widget.keys():
                self.widget.configure(text=t)
            elif 'placeholder_text' in self.widget.keys():
                self.widget.configure(placeholder_text=t)
        return None

    def _clear(self):
        if hasattr(self.widget, 'delete'):
            self.widget.delete(0, 'end')
        return None

class GxObject:
    """The gx built-in object, always available in Grynk."""

    def __init__(self):
        self._gui = None
        global _GX_INSTANCE
        _GX_INSTANCE = self

    # ── GUI ───────────────────────────────────────────────────────────────────

    def window(self, title="Grynk App", width=400, height=300):
        ctk = _try_import('customtkinter')
        if ctk:
            ctk.set_appearance_mode("dark")
            ctk.set_default_color_theme("blue")
            root = ctk.CTk()
        else:
            import tkinter as tk
            root = tk.Tk()
        
        root.title(unwrap(title))
        root.geometry(f"{int(unwrap(width))}x{int(unwrap(height))}")
        self._gui = GxGUI(root)
        return self._gui

    def button(self, text, callback):
        if not self._gui:
            raise GrynkRuntimeError("gx.button requires an active window (call gx.window first)")
        return self._gui.add_button(text, callback)

    def label(self, text):
        if not self._gui:
            raise GrynkRuntimeError("gx.label requires an active window")
        return self._gui.add_label(text)

    def entry(self, placeholder=""):
        if not self._gui:
            raise GrynkRuntimeError("gx.entry requires an active window")
        return self._gui.add_entry(placeholder)

    def gui_run(self):
        if not self._gui:
            raise GrynkRuntimeError("gx.gui_run requires an active window")
        self._gui.run()

    # ── Randomness ────────────────────────────────────────────────────────────

    def rand(self):
        return random.random()

    def randint(self, a, b):
        return random.randint(int(unwrap(a)), int(unwrap(b)))

    def choice(self, lst):
        data = lst.data if isinstance(lst, GrynkList) else list(lst)
        return random.choice(data) if data else None

    def shuffle(self, lst):
        data = list(lst.data if isinstance(lst, GrynkList) else lst)
        random.shuffle(data)
        return GrynkList(data)

    def uuid(self):
        return GrynkString(str(uuid.uuid4()))

    def uid(self, n=8):
        n = int(unwrap(n))
        return GrynkString(uuid.uuid4().hex[:n])

    def token(self, n=32):
        import secrets
        n = int(unwrap(n))
        return GrynkString(secrets.token_hex(n // 2)[:n])

    # ── Web / HTTP ─────────────────────────────────────────────────────────────

    def fetch(self, url):
        requests = _try_import('requests')
        if requests is None:
            raise GrynkRuntimeError("gx.fetch requires 'requests' (pip install requests)")
        try:
            r = requests.get(unwrap(url), timeout=15)
            return _build_response(r)
        except Exception as e:
            raise GrynkRuntimeError(f"gx.fetch failed: {e}")

    def get(self, url, params=None, headers=None):
        requests = _try_import('requests')
        if requests is None:
            raise GrynkRuntimeError("gx.get requires 'requests' (pip install requests)")
        try:
            p = unwrap(params) if params is not None else None
            h = unwrap(headers) if headers is not None else None
            r = requests.get(unwrap(url), params=p, headers=h, timeout=15)
            return _build_response(r)
        except Exception as e:
            raise GrynkRuntimeError(f"gx.get failed: {e}")

    def post(self, url, body=None, headers=None):
        requests = _try_import('requests')
        if requests is None:
            raise GrynkRuntimeError("gx.post requires 'requests' (pip install requests)")
        try:
            b = unwrap(body) if body is not None else None
            h = unwrap(headers) if headers is not None else {}
            
            # Ensure all keys and values in headers are unwrapped strings
            clean_headers = {str(k): str(v) for k, v in h.items()}
            
            if isinstance(b, dict):
                if 'Content-Type' not in clean_headers:
                    clean_headers['Content-Type'] = 'application/json'
                r = requests.post(unwrap(url), json=b, headers=clean_headers, timeout=15)
            else:
                r = requests.post(unwrap(url), data=b, headers=clean_headers, timeout=15)
            return _build_response(r)
        except Exception as e:
            raise GrynkRuntimeError(f"gx.post failed: {e}")

    def scrape(self, url, tag):
        requests = _try_import('requests')
        bs4 = _try_import('bs4')
        if requests is None or bs4 is None:
            raise GrynkRuntimeError("gx.scrape requires 'requests' and 'beautifulsoup4'")
        try:
            r = requests.get(unwrap(url), timeout=15)
            soup = bs4.BeautifulSoup(r.text, 'html.parser')
            elements = soup.find_all(unwrap(tag))
            return GrynkList([GrynkString(e.get_text(strip=True)) for e in elements])
        except Exception as e:
            raise GrynkRuntimeError(f"gx.scrape failed: {e}")

    def url_encode(self, s):
        from urllib.parse import quote_plus
        return GrynkString(quote_plus(unwrap(s)))

    def url_decode(self, s):
        from urllib.parse import unquote_plus
        return GrynkString(unquote_plus(unwrap(s)))

    # ── AI ────────────────────────────────────────────────────────────────────

    def ai(self, prompt):
        openai = _try_import('openai')
        if openai is not None:
            api_key = os.environ.get('OPENAI_API_KEY')
            if api_key:
                try:
                    client = openai.OpenAI(api_key=api_key)
                    resp = client.chat.completions.create(
                        model='gpt-3.5-turbo',
                        messages=[{'role': 'user', 'content': unwrap(prompt)}],
                        max_tokens=500
                    )
                    return GrynkString(resp.choices[0].message.content)
                except Exception:
                    pass
        return _ai_fallback(prompt)

    def ai_sentiment(self, text):
        return _ai_sentiment(text)

    def ai_summarize(self, text, n=3):
        return _ai_summarize(text, n)

    def ai_translate(self, text, lang):
        return _ai_translate(text, lang)

    def ai_classify(self, text, labels):
        return _ai_classify(text, labels)

    def ai_code(self, description, language='python'):
        return _ai_code(description, language)

    # ── Crypto ────────────────────────────────────────────────────────────────

    def hash(self, s):
        return GrynkString(hashlib.sha256(unwrap(s).encode()).hexdigest())

    def md5(self, s):
        return GrynkString(hashlib.md5(unwrap(s).encode()).hexdigest())

    def sha256(self, s):
        return GrynkString(hashlib.sha256(unwrap(s).encode()).hexdigest())

    def hmac(self, key, msg):
        import hmac as _h
        h = _h.new(unwrap(key).encode(), unwrap(msg).encode(), hashlib.sha256)
        return GrynkString(h.hexdigest())

    def b64encode(self, s):
        encoded = base64.b64encode(unwrap(s).encode()).decode()
        return GrynkString(encoded)

    def b64decode(self, s):
        decoded = base64.b64decode(unwrap(s).encode()).decode()
        return GrynkString(decoded)

    # ── Time ──────────────────────────────────────────────────────────────────

    def now(self):
        return GrynkString(datetime.now().isoformat())

    def nowms(self):
        return int(time.time() * 1000)

    def date(self):
        return GrynkString(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

    def today(self):
        return GrynkString(datetime.now().strftime('%Y-%m-%d'))

    def sleep(self, ms):
        time.sleep(unwrap(ms) / 1000)
        return None

    def timer(self):
        return time.time()

    def bench(self, fn, runs=100):
        runs = int(unwrap(runs))
        start = time.perf_counter()
        for _ in range(runs):
            if callable(fn):
                fn()
        elapsed = (time.perf_counter() - start) * 1000
        return elapsed

    # ── Files ─────────────────────────────────────────────────────────────────

    def read(self, path):
        try:
            with open(unwrap(path), 'r', encoding='utf-8') as f:
                return GrynkString(f.read())
        except Exception as e:
            raise GrynkRuntimeError(f"gx.read failed: {e}")

    def write(self, path, content):
        try:
            with open(unwrap(path), 'w', encoding='utf-8') as f:
                f.write(grynk_str(content))
            return True
        except Exception as e:
            raise GrynkRuntimeError(f"gx.write failed: {e}")

    def append(self, path, content):
        try:
            with open(unwrap(path), 'a', encoding='utf-8') as f:
                f.write(grynk_str(content))
            return True
        except Exception as e:
            raise GrynkRuntimeError(f"gx.append failed: {e}")

    def read_json(self, path):
        try:
            with open(unwrap(path), 'r', encoding='utf-8') as f:
                return wrap(json.load(f))
        except Exception as e:
            raise GrynkRuntimeError(f"gx.read_json failed: {e}")

    def write_json(self, path, data):
        try:
            with open(unwrap(path), 'w', encoding='utf-8') as f:
                json.dump(unwrap(data), f, indent=2)
            return True
        except Exception as e:
            raise GrynkRuntimeError(f"gx.write_json failed: {e}")

    def file_exists(self, path):
        return os.path.exists(unwrap(path))

    def list_dir(self, path='.'):
        try:
            entries = os.listdir(unwrap(path))
            return GrynkList([GrynkString(e) for e in entries])
        except Exception as e:
            raise GrynkRuntimeError(f"gx.list_dir failed: {e}")

    def make_dir(self, path):
        try:
            os.makedirs(unwrap(path), exist_ok=True)
            return True
        except Exception as e:
            raise GrynkRuntimeError(f"gx.make_dir failed: {e}")

    def delete(self, path):
        p = unwrap(path)
        try:
            if os.path.isdir(p):
                shutil.rmtree(p)
            else:
                os.remove(p)
            return True
        except Exception as e:
            raise GrynkRuntimeError(f"gx.delete failed: {e}")

    # ── Terminal output ───────────────────────────────────────────────────────

    def color(self, color, text):
        return GrynkString(_colorize(unwrap(color), unwrap(text)))

    def log(self, msg, level='info'):
        levels = {
            'info':    _colorize('cyan',   '[INFO]'),
            'warn':    _colorize('yellow', '[WARN]'),
            'error':   _colorize('red',    '[ERROR]'),
            'success': _colorize('green',  '[OK]'),
            'debug':   _colorize('magenta','[DEBUG]'),
        }
        lvl = levels.get(unwrap(level).lower(), '[LOG]')
        print(f"{lvl} {grynk_str(msg)}")
        return None

    def banner(self, text, color='cyan'):
        text = unwrap(text)
        color = unwrap(color)
        width = max(len(text) + 4, 30)
        border = '═' * width
        pad = ' ' * ((width - len(text) - 2) // 2)
        lines = [
            _colorize(color, f'╔{border}╗'),
            _colorize(color, f'║{pad} {text} {pad}║'),
            _colorize(color, f'╚{border}╝'),
        ]
        print('\n'.join(lines))
        return None

    def table(self, data):
        if isinstance(data, GrynkList):
            rows = data.data
        elif isinstance(data, list):
            rows = data
        else:
            rows = [data]

        if not rows:
            print('(empty table)')
            return None

        # Get column headers from first row
        first = rows[0]
        if isinstance(first, GrynkDict):
            headers = [grynk_str(k) for k in first.data.keys()]
            table_rows = []
            for row in rows:
                if isinstance(row, GrynkDict):
                    table_rows.append([grynk_str(v) for v in row.data.values()])
                else:
                    table_rows.append([grynk_str(row)])
        elif isinstance(first, GrynkList):
            headers = [str(i) for i in range(len(first.data))]
            table_rows = [[grynk_str(v) for v in row.data] for row in rows if isinstance(row, GrynkList)]
        else:
            for row in rows:
                print(' | '.join(grynk_str(v) for v in (row.data if isinstance(row, GrynkList) else [row])))
            return None

        col_widths = [max(len(h), max((len(r[i]) if i < len(r) else 0) for r in table_rows)) for i, h in enumerate(headers)]
        sep = '┼'.join('─' * (w + 2) for w in col_widths)
        header_row = '│'.join(f' {h:{w}} ' for h, w in zip(headers, col_widths))
        print(f'┌{sep.replace("┼", "┬")}┐')
        print(f'│{header_row}│')
        print(f'├{sep}┤')
        for row in table_rows:
            row_str = '│'.join(f' {(row[i] if i < len(row) else ""):{w}} ' for i, w in enumerate(col_widths))
            print(f'│{row_str}│')
        print(f'└{sep.replace("┼", "┴")}┘')
        return None

    def progress(self, current, total):
        current = int(unwrap(current))
        total = int(unwrap(total))
        pct = current / total if total else 0
        bar_len = 40
        filled = int(bar_len * pct)
        bar = '█' * filled + '░' * (bar_len - filled)
        print(f'\r[{bar}] {pct*100:.1f}% ({current}/{total})', end='', flush=True)
        if current >= total:
            print()
        return None

    def spinner(self, msg, seconds=1.0):
        import itertools
        frames = ['⠋','⠙','⠹','⠸','⠼','⠴','⠦','⠧','⠇','⠏']
        end = time.time() + float(unwrap(seconds))
        for f in itertools.cycle(frames):
            if time.time() >= end:
                break
            print(f'\r{_colorize("cyan", f)} {unwrap(msg)}', end='', flush=True)
            time.sleep(0.08)
        print()
        return None

    def clear(self):
        os.system('cls' if os.name == 'nt' else 'clear')
        return None

    # ── Math ──────────────────────────────────────────────────────────────────

    def sqrt(self, n): return math.sqrt(unwrap(n))
    def abs(self, n): return builtins_abs(unwrap(n))
    def floor(self, n): return int(math.floor(unwrap(n)))
    def ceil(self, n): return int(math.ceil(unwrap(n)))
    def round(self, n, d=0): return builtins_round(unwrap(n), int(unwrap(d)))
    def clamp(self, v, lo, hi): return max(unwrap(lo), min(unwrap(v), unwrap(hi)))
    def lerp(self, a, b, t): a,b,t=unwrap(a),unwrap(b),unwrap(t); return a + (b-a)*t
    def map_range(self, v, in_min, in_max, out_min, out_max):
        v,i0,i1,o0,o1 = unwrap(v),unwrap(in_min),unwrap(in_max),unwrap(out_min),unwrap(out_max)
        return o0 + (v - i0) / (i1 - i0) * (o1 - o0)

    def avg(self, lst):
        data = lst.data if isinstance(lst, GrynkList) else list(lst)
        nums = [unwrap(e) for e in data if isinstance(unwrap(e), (int, float))]
        return sum(nums) / len(nums) if nums else 0

    def sum(self, lst):
        data = lst.data if isinstance(lst, GrynkList) else list(lst)
        return builtins_sum(unwrap(e) for e in data if isinstance(unwrap(e), (int, float)))

    def min(self, *args):
        if len(args) == 1:
            lst = args[0]
            data = lst.data if isinstance(lst, GrynkList) else list(lst)
            return builtins_min(unwrap(e) for e in data)
        return builtins_min(unwrap(a) for a in args)

    def max(self, *args):
        if len(args) == 1:
            lst = args[0]
            data = lst.data if isinstance(lst, GrynkList) else list(lst)
            return builtins_max(unwrap(e) for e in data)
        return builtins_max(unwrap(a) for a in args)

    def pi(self): return math.pi
    def e(self): return math.e

    # ── Data ──────────────────────────────────────────────────────────────────

    def range(self, a, b=None):
        if b is None:
            return GrynkList(list(builtins_range(int(unwrap(a)))))
        return GrynkList(list(builtins_range(int(unwrap(a)), int(unwrap(b)))))

    def sort(self, lst, key=None):
        data = list(lst.data if isinstance(lst, GrynkList) else lst)
        if key and callable(key):
            data = sorted(data, key=lambda x: unwrap(key(x)))
        else:
            data = sorted(data, key=lambda x: (str(type(unwrap(x))), unwrap(x)))
        return GrynkList(data)

    def unique(self, lst):
        data = lst.data if isinstance(lst, GrynkList) else list(lst)
        seen = []
        result = []
        for e in data:
            u = unwrap(e)
            if u not in seen:
                seen.append(u)
                result.append(e)
        return GrynkList(result)

    def chunk(self, lst, n):
        data = lst.data if isinstance(lst, GrynkList) else list(lst)
        n = int(unwrap(n))
        return GrynkList([GrynkList(data[i:i+n]) for i in builtins_range(0, len(data), n)])

    def flatten(self, lst):
        from .types import _flatten
        data = lst.data if isinstance(lst, GrynkList) else list(lst)
        return GrynkList(_flatten(data))

    def group_by(self, lst, key_fn):
        data = lst.data if isinstance(lst, GrynkList) else list(lst)
        groups = {}
        for e in data:
            k = grynk_str(key_fn(e) if callable(key_fn) else e)
            groups.setdefault(k, []).append(e)
        return GrynkDict({GrynkString(k): GrynkList(v) for k, v in groups.items()})

    def map(self, fn, lst):
        data = lst.data if isinstance(lst, GrynkList) else list(lst)
        return GrynkList([fn(e) for e in data])

    def filter(self, fn, lst):
        data = lst.data if isinstance(lst, GrynkList) else list(lst)
        return GrynkList([e for e in data if grynk_bool(fn(e))])

    def reduce(self, fn, lst, init=None):
        data = lst.data if isinstance(lst, GrynkList) else list(lst)
        acc = init
        for e in data:
            acc = fn(acc, e)
        return acc

    def first(self, lst):
        data = lst.data if isinstance(lst, GrynkList) else list(lst)
        return data[0] if data else None

    def last(self, lst):
        data = lst.data if isinstance(lst, GrynkList) else list(lst)
        return data[-1] if data else None

    def reverse(self, lst):
        data = lst.data if isinstance(lst, GrynkList) else list(lst)
        return GrynkList(list(reversed(data)))

    def zip(self, lists):
        iters = [(l.data if isinstance(l, GrynkList) else list(l))
                 for l in (lists.data if isinstance(lists, GrynkList) else lists)]
        return GrynkList([GrynkList(list(row)) for row in builtins_zip(*iters)])

    # ── OS / System ───────────────────────────────────────────────────────────

    def env(self, key):
        val = os.environ.get(unwrap(key))
        return GrynkString(val) if val is not None else None

    def set_env(self, key, val):
        os.environ[unwrap(key)] = unwrap(val)
        return None

    def run(self, cmd):
        try:
            result = subprocess.run(
                unwrap(cmd), shell=True, capture_output=True, text=True
            )
            return GrynkString(result.stdout + result.stderr)
        except Exception as e:
            raise GrynkRuntimeError(f"gx.run failed: {e}")

    def cwd(self):
        return GrynkString(os.getcwd())

    def platform(self):
        return GrynkString(_platform.system().lower())

    def args(self):
        return GrynkList([GrynkString(a) for a in sys.argv[1:]])

    def exit(self, code=0):
        sys.exit(int(unwrap(code)))

    # ── Type tools ────────────────────────────────────────────────────────────

    def type_of(self, v):
        if v is None: return GrynkString('null')
        if isinstance(v, bool): return GrynkString('bool')
        if isinstance(v, int): return GrynkString('int')
        if isinstance(v, float): return GrynkString('float')
        if isinstance(v, GrynkString): return GrynkString('string')
        if isinstance(v, GrynkList): return GrynkString('list')
        if isinstance(v, GrynkDict): return GrynkString('dict')
        if callable(v): return GrynkString('function')
        return GrynkString(type(v).__name__)

    def to_int(self, v):
        try: return int(float(str(unwrap(v))))
        except: return 0

    def to_float(self, v):
        try: return float(str(unwrap(v)))
        except: return 0.0

    def to_str(self, v):
        return GrynkString(grynk_str(v))

    def to_bool(self, v):
        return grynk_bool(v)

    def is_int(self, v): return isinstance(v, int) and not isinstance(v, bool)
    def is_str(self, v): return isinstance(v, (str, GrynkString))
    def is_list(self, v): return isinstance(v, GrynkList)
    def is_null(self, v): return v is None

    # ── String utilities ──────────────────────────────────────────────────────

    def slugify(self, s):
        s = unwrap(s).lower()
        s = re.sub(r'[^a-z0-9\s-]', '', s)
        s = re.sub(r'[\s]+', '-', s.strip())
        return GrynkString(s)

    def truncate(self, s, n):
        s = unwrap(s)
        n = int(unwrap(n))
        return GrynkString(s[:n] + ('…' if len(s) > n else ''))

    def regex_match(self, pattern, text):
        m = re.match(unwrap(pattern), unwrap(text))
        return m is not None

    def regex_find(self, pattern, text):
        results = re.findall(unwrap(pattern), unwrap(text))
        return GrynkList([GrynkString(r) if isinstance(r, str) else GrynkList([GrynkString(g) for g in r]) for r in results])

    def regex_replace(self, pattern, replacement, text):
        return GrynkString(re.sub(unwrap(pattern), unwrap(replacement), unwrap(text)))

    def join(self, lst, sep=''):
        data = lst.data if isinstance(lst, GrynkList) else list(lst)
        return GrynkString(unwrap(sep).join(grynk_str(e) for e in data))

    def split(self, s, sep=None):
        parts = unwrap(s).split(unwrap(sep) if sep is not None else None)
        return GrynkList([GrynkString(p) for p in parts])

    # ── Concurrency ───────────────────────────────────────────────────────────

    def spawn(self, fn):
        results = [None]
        errors = [None]
        def _run():
            try:
                results[0] = fn() if callable(fn) else None
            except Exception as e:
                errors[0] = e
        t = threading.Thread(target=_run, daemon=True)
        t.start()
        t._grynk_results = results
        t._grynk_errors = errors
        return t

    def wait(self, thread):
        if isinstance(thread, threading.Thread):
            thread.join()
            if thread._grynk_errors[0]:
                raise GrynkRuntimeError(f"Spawned thread error: {thread._grynk_errors[0]}")
            return thread._grynk_results[0]
        return None

    # ── Method dispatch ───────────────────────────────────────────────────────

    def get_attr(self, name):
        """Return a gx.method as a Python callable."""
        if hasattr(self, name):
            attr = getattr(self, name)
            if callable(attr):
                return attr
        raise GrynkRuntimeError(f"gx has no method '{name}'")


# Aliases for Python builtins we shadowed
import builtins
builtins_abs   = builtins.abs
builtins_round = builtins.round
builtins_sum   = builtins.sum
builtins_min   = builtins.min
builtins_max   = builtins.max
builtins_range = builtins.range
builtins_zip   = builtins.zip

# Singleton
gx = GxObject()
