"""Grynk runtime types — wraps Python values with Grynk method dispatch."""

from .errors import GrynkRuntimeError, GrynkTypeError


def grynk_str(v):
    """Convert any Grynk value to its string representation."""
    if v is None:
        return 'null'
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if isinstance(v, GrynkList):
        return '[' + ', '.join(grynk_str(e) for e in v.data) + ']'
    if isinstance(v, GrynkDict):
        items = ', '.join(f'{grynk_str(k)}: {grynk_str(v2)}' for k, v2 in v.data.items())
        return '{' + items + '}'
    if isinstance(v, GrynkString):
        return v.data
    if isinstance(v, GrynkNum):
        return grynk_str(v.data)
    if isinstance(v, float) and v == int(v):
        return str(int(v))
    return str(v)


def grynk_bool(v):
    if v is None: return False
    if isinstance(v, bool): return v
    if isinstance(v, (int, float)): return v != 0
    if isinstance(v, str): return len(v) > 0
    if isinstance(v, GrynkString): return len(v.data) > 0
    if isinstance(v, GrynkList): return len(v.data) > 0
    if isinstance(v, GrynkDict): return len(v.data) > 0
    return True


def wrap(v):
    """Wrap a Python value into the appropriate Grynk type."""
    if isinstance(v, (GrynkString, GrynkList, GrynkDict, GrynkNum)):
        return v
    if isinstance(v, str):
        return GrynkString(v)
    if isinstance(v, list):
        return GrynkList([wrap(e) for e in v])
    if isinstance(v, dict):
        return GrynkDict({k: wrap(val) for k, val in v.items()})
    if isinstance(v, bool):
        return v  # keep as Python bool
    if isinstance(v, (int, float)):
        return v  # keep as Python number — wrap only when method accessed
    return v


def unwrap(v):
    """Convert Grynk wrapped type back to Python primitive."""
    if isinstance(v, GrynkString): return v.data
    if isinstance(v, GrynkList): return [unwrap(e) for e in v.data]
    if isinstance(v, GrynkDict): return {unwrap(k): unwrap(val) for k, val in v.data.items()}
    if isinstance(v, GrynkNum): return v.data
    return v


# ── GrynkString ───────────────────────────────────────────────────────────────

class GrynkString:
    def __init__(self, data: str):
        self.data = data

    def __repr__(self): return f'GrynkString({self.data!r})'
    def __str__(self): return self.data
    def __eq__(self, other):
        if isinstance(other, GrynkString): return self.data == other.data
        if isinstance(other, str): return self.data == other
        return False
    def __hash__(self): return hash(self.data)
    def __add__(self, other): return GrynkString(self.data + grynk_str(other))
    def __bool__(self): return bool(self.data)

    def get_method(self, name, line=None):
        data = self.data
        methods = {
            'upper':    lambda: GrynkString(data.upper()),
            'lower':    lambda: GrynkString(data.lower()),
            'trim':     lambda: GrynkString(data.strip()),
            'len':      lambda: len(data),
            'reverse':  lambda: GrynkString(data[::-1]),
            'lines':    lambda: GrynkList([GrynkString(l) for l in data.splitlines()]),
            'chars':    lambda: GrynkList([GrynkString(c) for c in data]),
            'encode':   lambda: GrynkList([b for b in data.encode('utf-8')]),
            'to_int':   lambda: int(data) if data.isdigit() else 0,
            'to_float': lambda: float(data),
            'hash':     lambda: _string_hash(data),
            'slug':     lambda: _slugify(data),
            'split':    lambda sep=None: GrynkList([GrynkString(p) for p in data.split(unwrap(sep) if sep else None)]),
            'replace':  lambda old, new: GrynkString(data.replace(unwrap(old), unwrap(new))),
            'contains': lambda s: unwrap(s) in data,
            'starts':   lambda s: data.startswith(unwrap(s)),
            'ends':     lambda s: data.endswith(unwrap(s)),
            'slice':    lambda a, b=None: GrynkString(data[unwrap(a) : (unwrap(b) if b is not None else None)]),
            'repeat':   lambda n: GrynkString(data * unwrap(n)),
            'truncate': lambda n: GrynkString(data[:unwrap(n)] + ('…' if len(data) > unwrap(n) else '')),
            'index_of': lambda s: data.find(unwrap(s)),
        }
        if name not in methods:
            raise GrynkRuntimeError(f"String has no method '{name}'", line=line)
        return methods[name]


# ── GrynkList ─────────────────────────────────────────────────────────────────

class GrynkList:
    def __init__(self, data: list):
        self.data = list(data)

    def __repr__(self): return f'GrynkList({self.data!r})'
    def __eq__(self, other):
        if isinstance(other, GrynkList): return self.data == other.data
        return False
    def __bool__(self): return bool(self.data)
    def __iter__(self): return iter(self.data)
    def __len__(self): return len(self.data)

    def get_method(self, name, line=None):
        data = self.data

        def _fn_map(fn, lst):
            return GrynkList([_call_fn(fn, [e]) for e in lst])
        def _fn_filter(fn, lst):
            return GrynkList([e for e in lst if grynk_bool(_call_fn(fn, [e]))])
        def _fn_reduce(fn, lst, init):
            acc = init
            for e in lst:
                acc = _call_fn(fn, [acc, e])
            return acc
        def _fn_find(fn, lst):
            for e in lst:
                if grynk_bool(_call_fn(fn, [e])): return e
            return None
        def _fn_sort(key=None):
            import functools
            def cmp_key(x):
                val = _call_fn(key, [x]) if key else x
                return unwrap(val) if not isinstance(val, (list, dict)) else str(val)
            return GrynkList(sorted(data, key=cmp_key))
        def _fn_each(fn):
            for e in data: _call_fn(fn, [e])
            return None

        methods = {
            'push':     lambda v: (data.append(v), self)[1],
            'pop':      lambda: data.pop() if data else None,
            'shift':    lambda: data.pop(0) if data else None,
            'unshift':  lambda v: (data.insert(0, v), self)[1],
            'len':      lambda: len(data),
            'get':      lambda idx, default=None: (data[int(unwrap(idx))] if 0 <= int(unwrap(idx)) < len(data) else default),
            'first':    lambda: data[0] if data else None,
            'last':     lambda: data[-1] if data else None,
            'reverse':  lambda: GrynkList(list(reversed(data))),
            'sort':     _fn_sort,
            'unique':   lambda: GrynkList(list({id(x) if isinstance(x, GrynkList) else unwrap(x): x for x in data}.values())),
            'flat':     lambda: GrynkList(_flatten(data)),
            'map':      lambda fn: _fn_map(fn, data),
            'filter':   lambda fn: _fn_filter(fn, data),
            'find':     lambda fn: _fn_find(fn, data),
            'reduce':   lambda fn, init=None: _fn_reduce(fn, data, init),
            'each':     _fn_each,
            'includes': lambda v: any(_grynk_eq(e, v) for e in data),
            'index_of': lambda v: next((i for i, e in enumerate(data) if _grynk_eq(e, v)), -1),
            'count':    lambda v: sum(1 for e in data if _grynk_eq(e, v)),
            'remove':   lambda v: (data.remove(next(e for e in data if _grynk_eq(e, v))), self)[1],
            'slice':    lambda a, b=None: GrynkList(data[unwrap(a): (unwrap(b) if b is not None else None)]),
            'chunk':    lambda n: GrynkList([GrynkList(data[i:i+unwrap(n)]) for i in range(0, len(data), unwrap(n))]),
            'join':     lambda sep='': GrynkString(grynk_str(sep).join(grynk_str(e) for e in data)),
            'copy':     lambda: GrynkList(list(data)),
            'extend':   lambda other: (data.extend((other.data if isinstance(other, GrynkList) else list(other))), self)[1],
            'clear':    lambda: (data.clear(), self)[1],
            'sum':      lambda: sum(unwrap(e) for e in data if isinstance(unwrap(e), (int, float))),
            'avg':      lambda: (sum(unwrap(e) for e in data) / len(data)) if data else 0,
            'min':      lambda: min(unwrap(e) for e in data),
            'max':      lambda: max(unwrap(e) for e in data),
        }
        if name not in methods:
            raise GrynkRuntimeError(f"List has no method '{name}'", line=line)
        return methods[name]


# ── GrynkDict ─────────────────────────────────────────────────────────────────

class GrynkDict:
    def __init__(self, data: dict):
        self.data = dict(data)

    def __repr__(self): return f'GrynkDict({self.data!r})'
    def __eq__(self, other):
        if isinstance(other, GrynkDict): return self.data == other.data
        return False
    def __bool__(self): return bool(self.data)

    def py_get(self, key, default=None):
        for k, v in self.data.items():
            if (isinstance(k, GrynkString) and k.data == key) or k == key:
                return v
        return default

    def py_set(self, key, value):
        for k in list(self.data.keys()):
            if (isinstance(k, GrynkString) and k.data == key) or k == key:
                self.data[k] = value
                return
        self.data[GrynkString(key) if isinstance(key, str) else key] = value

    def get_method(self, name, line=None):
        data = self.data
        methods = {
            'keys':   lambda: GrynkList([GrynkString(unwrap(k)) if not isinstance(k, GrynkString) else k for k in data.keys()]),
            'values': lambda: GrynkList(list(data.values())),
            'items':  lambda: GrynkList([GrynkList([k, v]) for k, v in data.items()]),
            'has':    lambda key: any((isinstance(k, GrynkString) and k.data == unwrap(key)) or k == unwrap(key) for k in data),
            'get':    lambda key, default=None: self.py_get(unwrap(key), default),
            'set':    lambda key, val: (self.py_set(unwrap(key), val), self)[1],
            'delete': lambda key: (data.pop(next(k for k in data if (isinstance(k, GrynkString) and k.data == unwrap(key)) or k == unwrap(key)), None), self)[1],
            'merge':  lambda other: GrynkDict({**data, **(other.data if isinstance(other, GrynkDict) else other)}),
            'len':    lambda: len(data),
        }
        if name not in methods:
            raise GrynkRuntimeError(f"Dict has no method '{name}'", line=line)
        return methods[name]


# ── GrynkNum ──────────────────────────────────────────────────────────────────

class GrynkNum:
    """Wraps a number to give it method access."""
    def __init__(self, data):
        self.data = data

    def get_method(self, name, line=None):
        import math
        n = self.data
        methods = {
            'to_str':  lambda: GrynkString(grynk_str(n)),
            'abs':     lambda: abs(n),
            'floor':   lambda: int(math.floor(n)),
            'ceil':    lambda: int(math.ceil(n)),
            'round':   lambda d=0: round(n, unwrap(d)),
            'sqrt':    lambda: math.sqrt(n),
            'pow':     lambda exp: n ** unwrap(exp),
            'clamp':   lambda lo, hi: max(unwrap(lo), min(n, unwrap(hi))),
        }
        if name not in methods:
            raise GrynkRuntimeError(f"Number has no method '{name}'", line=line)
        return methods[name]


# ── Response (for gx.fetch / gx.get / gx.post) ────────────────────────────────

class GrynkResponse:
    def __init__(self, text, status, ok, json_data=None):
        self._text = GrynkString(text)
        self._status = status
        self._ok = ok
        self._json = None
        if json_data is not None:
            self._json = wrap(json_data)

    def get_attr(self, name, line=None):
        if name == 'text': return self._text
        if name == 'status': return self._status
        if name == 'ok': return self._ok
        if name == 'json': return self._json
        raise GrynkRuntimeError(f"Response has no attribute '{name}'", line=line)


# ── helpers ───────────────────────────────────────────────────────────────────

def _call_fn(fn, args):
    """Call a Grynk callable (GrynkFunction / lambda) or Python callable."""
    if callable(fn):
        return fn(*args)
    raise GrynkRuntimeError(f"Not callable: {fn!r}")


def _grynk_eq(a, b):
    return unwrap(a) == unwrap(b)


def _flatten(lst):
    result = []
    for item in lst:
        if isinstance(item, GrynkList):
            result.extend(_flatten(item.data))
        else:
            result.append(item)
    return result


def _slugify(s):
    import re
    s = s.lower()
    s = re.sub(r'[^a-z0-9\s-]', '', s)
    s = re.sub(r'[\s]+', '-', s.strip())
    return GrynkString(s)


def _string_hash(s):
    import hashlib
    return GrynkString(hashlib.sha256(s.encode()).hexdigest())
