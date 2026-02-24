"""Grynk Interpreter — tree-walk evaluator."""

from .parser import (
    Program, VarDecl, Assign, FnDecl, Return, Say, If, Loop, ForIn,
    While, Break, Continue, TryCatch, Throw, Match, BinOp, UnaryOp,
    Literal, ListLiteral, DictLiteral, StringInterp, Ident, Call,
    Attr, Index, Pipe, Lambda, ExprStmt
)
from .types import (
    GrynkString, GrynkList, GrynkDict, GrynkNum, GrynkResponse,
    wrap, unwrap, grynk_str, grynk_bool
)
from .errors import (
    GrynkRuntimeError, GrynkTypeError, GrynkNameError, GrynkError
)
from .gx import gx


# ── Control flow signals (raised as exceptions) ────────────────────────────────

class ReturnSignal(Exception):
    def __init__(self, value): self.value = value

class BreakSignal(Exception): pass
class ContinueSignal(Exception): pass


# ── Grynk Function ─────────────────────────────────────────────────────────────

class GrynkFunction:
    def __init__(self, name, params, body, closure_env):
        self.name = name
        self.params = params   # list of (name, default_node | None)
        self.body = body
        self.closure_env = closure_env

    def __repr__(self):
        return f'<fn {self.name}>'


# ── Environment ────────────────────────────────────────────────────────────────

class Environment:
    def __init__(self, parent=None):
        self._vars = {}
        self._parent = parent

    def get(self, name):
        if name in self._vars:
            return self._vars[name]
        if self._parent is not None:
            return self._parent.get(name)
        return None  # not found sentinel

    def has(self, name):
        if name in self._vars:
            return True
        if self._parent is not None:
            return self._parent.has(name)
        return False

    def set(self, name, value):
        """Set in the nearest scope where name already exists, else current."""
        if name in self._vars:
            self._vars[name] = value
            return
        if self._parent is not None and self._parent.has(name):
            self._parent.set(name, value)
            return
        self._vars[name] = value

    def define(self, name, value):
        """Always define in current scope."""
        self._vars[name] = value

    def all_names(self):
        names = list(self._vars.keys())
        if self._parent:
            names += self._parent.all_names()
        return names


# ── Interpreter ────────────────────────────────────────────────────────────────

class Interpreter:
    def __init__(self):
        self.globals = Environment()
        self._setup_globals()

    def _setup_globals(self):
        """Populate the global environment with built-ins."""
        self.globals.define('gx', gx)

        # ask() built-in
        def _ask(prompt=None):
            try:
                return GrynkString(input(grynk_str(prompt) if prompt is not None else ''))
            except (EOFError, KeyboardInterrupt):
                return GrynkString('')
        self.globals.define('ask', _ask)

        # Common standalone functions
        self.globals.define('print', lambda *a: print(*[grynk_str(x) for x in a]))
        self.globals.define('len', lambda v: (
            len(v.data) if isinstance(v, (GrynkString, GrynkList, GrynkDict)) else len(v)
        ))
        self.globals.define('type', lambda v: GrynkString(self._type_name(v)))
        self.globals.define('int', lambda v: int(unwrap(v)) if v is not None else 0)
        self.globals.define('float', lambda v: float(unwrap(v)) if v is not None else 0.0)
        
        def _num(v):
            raw = unwrap(v)
            if isinstance(raw, (int, float)): return raw
            try:
                s = str(raw)
                return float(s) if '.' in s or 'e' in s.lower() else int(s)
            except:
                return 0
        self.globals.define('num', _num)
        
        self.globals.define('str', lambda v: GrynkString(grynk_str(v)))
        self.globals.define('bool', lambda v: grynk_bool(v))

    def _type_name(self, v):
        if v is None: return 'null'
        if isinstance(v, bool): return 'bool'
        if isinstance(v, int): return 'int'
        if isinstance(v, float): return 'float'
        if isinstance(v, GrynkString): return 'string'
        if isinstance(v, GrynkList): return 'list'
        if isinstance(v, GrynkDict): return 'dict'
        if isinstance(v, GrynkFunction): return 'function'
        if callable(v): return 'function'
        return type(v).__name__

    # ── execution entry ────────────────────────────────────────────────────────

    def run(self, program):
        return self.exec_block(program.body, self.globals)

    def exec_block(self, stmts, env):
        result = None
        for stmt in stmts:
            result = self.exec(stmt, env)
        return result

    def exec(self, node, env):
        meth = getattr(self, f'_exec_{type(node).__name__}', None)
        if meth is None:
            raise GrynkRuntimeError(f"Unknown AST node: {type(node).__name__}", line=getattr(node, 'line', None))
        return meth(node, env)

    # ── statements ──────────────────────────────────────────────────────────────

    def _exec_Program(self, node, env):
        return self.exec_block(node.body, env)

    def _exec_VarDecl(self, node, env):
        value = self.eval(node.value, env)
        env.define(node.name, value)
        return None

    def _exec_Assign(self, node, env):
        # evaluate target to figure out where to write
        new_val = self.eval(node.value, env)
        if node.op == '+=':
            cur = self._resolve_lvalue(node.target, env)
            new_val = self._binop('+', cur, new_val, node.line)
        elif node.op == '-=':
            cur = self._resolve_lvalue(node.target, env)
            new_val = self._binop('-', cur, new_val, node.line)
        self._write_lvalue(node.target, new_val, env, node.line)
        return None

    def _resolve_lvalue(self, target, env):
        return self.eval(target, env)

    def _write_lvalue(self, target, value, env, line=None):
        from .parser import Ident, Attr, Index
        if isinstance(target, Ident):
            if not env.has(target.name):
                raise GrynkNameError(target.name, line=line, known_names=env.all_names())
            env.set(target.name, value)
        elif isinstance(target, Attr):
            obj = self.eval(target.obj, env)
            if isinstance(obj, GrynkDict):
                obj.py_set(target.name, value)
            else:
                raise GrynkRuntimeError(f"Cannot set attribute '{target.name}' on {self._type_name(obj)}", line=line)
        elif isinstance(target, Index):
            obj = self.eval(target.obj, env)
            key = self.eval(target.key, env)
            if isinstance(obj, GrynkList):
                obj.data[int(unwrap(key))] = value
            elif isinstance(obj, GrynkDict):
                obj.py_set(unwrap(key), value)
            else:
                raise GrynkRuntimeError("Cannot index into this type", line=line)
        else:
            raise GrynkRuntimeError("Invalid assignment target", line=line)

    def _exec_FnDecl(self, node, env):
        fn = GrynkFunction(node.name, node.params, node.body, env)
        callable_fn = self._make_callable(fn)
        env.define(node.name, callable_fn)
        return None

    def _exec_Return(self, node, env):
        value = self.eval(node.value, env) if node.value is not None else None
        raise ReturnSignal(value)

    def _exec_Say(self, node, env):
        value = self.eval(node.value, env)
        print(grynk_str(value))
        return None

    def _exec_If(self, node, env):
        if grynk_bool(self.eval(node.condition, env)):
            child = Environment(env)
            return self.exec_block(node.then_body, child)
        for cond, body in node.elif_clauses:
            if grynk_bool(self.eval(cond, env)):
                child = Environment(env)
                return self.exec_block(body, child)
        if node.else_body is not None:
            child = Environment(env)
            return self.exec_block(node.else_body, child)
        return None

    def _exec_Loop(self, node, env):
        count = int(unwrap(self.eval(node.count, env)))
        for _ in range(count):
            child = Environment(env)
            try:
                self.exec_block(node.body, child)
            except BreakSignal:
                break
            except ContinueSignal:
                continue
        return None

    def _exec_ForIn(self, node, env):
        iterable = self.eval(node.iterable, env)
        if isinstance(iterable, GrynkList):
            items = iterable.data
        elif isinstance(iterable, GrynkString):
            items = [GrynkString(c) for c in iterable.data]
        elif isinstance(iterable, GrynkDict):
            items = list(iterable.data.keys())
        else:
            items = list(iterable)
        for item in items:
            child = Environment(env)
            child.define(node.var, item)
            try:
                self.exec_block(node.body, child)
            except BreakSignal:
                break
            except ContinueSignal:
                continue
        return None

    def _exec_While(self, node, env):
        while grynk_bool(self.eval(node.condition, env)):
            child = Environment(env)
            try:
                self.exec_block(node.body, child)
            except BreakSignal:
                break
            except ContinueSignal:
                continue
        return None

    def _exec_Break(self, node, env):
        raise BreakSignal()

    def _exec_Continue(self, node, env):
        raise ContinueSignal()

    def _exec_TryCatch(self, node, env):
        try:
            child = Environment(env)
            self.exec_block(node.try_body, child)
        except ReturnSignal:
            raise
        except BreakSignal:
            raise
        except ContinueSignal:
            raise
        except GrynkError as e:
            child = Environment(env)
            if node.err_name:
                child.define(node.err_name, GrynkString(str(e.message)))
            self.exec_block(node.catch_body, child)
        except Exception as e:
            child = Environment(env)
            if node.err_name:
                child.define(node.err_name, GrynkString(str(e)))
            self.exec_block(node.catch_body, child)
        return None

    def _exec_Throw(self, node, env):
        value = self.eval(node.value, env)
        raise GrynkRuntimeError(grynk_str(value), line=node.line)

    def _exec_Match(self, node, env):
        subject = self.eval(node.subject, env)
        for case_val, case_body in node.cases:
            cv = self.eval(case_val, env)
            if self._grynk_equal(subject, cv):
                child = Environment(env)
                return self.exec_block(case_body, child)
        if node.default is not None:
            child = Environment(env)
            return self.exec_block(node.default, child)
        return None

    def _exec_ExprStmt(self, node, env):
        return self.eval(node.expr, env)

    # ── expressions ──────────────────────────────────────────────────────────

    def eval(self, node, env):
        meth = getattr(self, f'_eval_{type(node).__name__}', None)
        if meth is None:
            raise GrynkRuntimeError(f"Cannot evaluate node: {type(node).__name__}",
                                    line=getattr(node, 'line', None))
        return meth(node, env)

    def _eval_Literal(self, node, env):
        v = node.value
        if isinstance(v, str):
            return GrynkString(v)
        return v

    def _eval_StringInterp(self, node, env):
        parts = []
        for kind, val in node.parts:
            if kind == 'lit':
                parts.append(val)
            else:
                parts.append(grynk_str(self.eval(val, env)))
        return GrynkString(''.join(parts))

    def _eval_ListLiteral(self, node, env):
        return GrynkList([self.eval(e, env) for e in node.elements])

    def _eval_DictLiteral(self, node, env):
        pairs = {}
        for k, v in node.pairs:
            key = self.eval(k, env)
            val = self.eval(v, env)
            pairs[key if isinstance(key, GrynkString) else GrynkString(grynk_str(key))] = val
        return GrynkDict(pairs)

    def _eval_Ident(self, node, env):
        if not env.has(node.name):
            raise GrynkNameError(node.name, line=node.line, known_names=env.all_names())
        return env.get(node.name)

    def _eval_BinOp(self, node, env):
        left = self.eval(node.left, env)
        # Short-circuit for boolean ops
        if node.op == 'and':
            return left if not grynk_bool(left) else self.eval(node.right, env)
        if node.op == 'or':
            return left if grynk_bool(left) else self.eval(node.right, env)
        right = self.eval(node.right, env)
        return self._binop(node.op, left, right, node.line)

    def _binop(self, op, left, right, line=None):
        # number coercion
        lraw = unwrap(left)
        rraw = unwrap(right)

        if op == '+':
            if isinstance(lraw, str) or isinstance(rraw, str):
                return GrynkString(grynk_str(left) + grynk_str(right))
            if isinstance(lraw, list) and isinstance(rraw, list):
                return GrynkList(lraw + rraw)
            return lraw + rraw
        if op == '-':  return lraw - rraw
        if op == '*':
            if isinstance(lraw, str) and isinstance(rraw, (int, float)):
                return GrynkString(lraw * int(rraw))
            return lraw * rraw
        if op == '/':
            if rraw == 0:
                raise GrynkRuntimeError("Division by zero", line=line)
            return lraw / rraw
        if op == '%':  return lraw % rraw
        if op == '**': return lraw ** rraw
        if op == '==': return self._grynk_equal(left, right)
        if op == '!=': return not self._grynk_equal(left, right)
        if op == '<':  return lraw < rraw
        if op == '>':  return lraw > rraw
        if op == '<=': return lraw <= rraw
        if op == '>=': return lraw >= rraw
        raise GrynkRuntimeError(f"Unknown operator '{op}'", line=line)

    def _grynk_equal(self, a, b):
        ua, ub = unwrap(a), unwrap(b)
        return ua == ub

    def _eval_UnaryOp(self, node, env):
        operand = self.eval(node.operand, env)
        if node.op == '-': return -unwrap(operand)
        if node.op == 'not': return not grynk_bool(operand)
        raise GrynkRuntimeError(f"Unknown unary op '{node.op}'", line=node.line)

    def _eval_Attr(self, node, env):
        obj = self.eval(node.obj, env)
        return self._get_attr(obj, node.name, node.line)

    def _get_attr(self, obj, name, line=None):
        # gx object
        if hasattr(obj, 'get_attr') and not isinstance(obj, (GrynkString, GrynkList, GrynkDict)):
            return obj.get_attr(name)
        # Response
        if isinstance(obj, GrynkResponse):
            return obj.get_attr(name, line)
        # Typed objects — return bound method
        if isinstance(obj, GrynkString):
            return obj.get_method(name, line)
        if isinstance(obj, GrynkList):
            return obj.get_method(name, line)
        if isinstance(obj, GrynkDict):
            return obj.get_method(name, line)
        if isinstance(obj, (int, float)) and not isinstance(obj, bool):
            return GrynkNum(obj).get_method(name, line)
        # dicts: try key lookup
        if isinstance(obj, dict):
            if name in obj:
                return obj[name]
        raise GrynkRuntimeError(f"Cannot access attribute '{name}' on {self._type_name(obj)}", line=line)

    def _eval_Index(self, node, env):
        obj = self.eval(node.obj, env)
        key = self.eval(node.key, env)
        return self._index(obj, key, node.line)

    def _index(self, obj, key, line=None):
        raw_key = unwrap(key)
        if isinstance(obj, GrynkList):
            try:
                return obj.data[int(raw_key)]
            except IndexError:
                raise GrynkRuntimeError(f"List index {raw_key} out of range", line=line)
        if isinstance(obj, GrynkDict):
            val = obj.py_get(raw_key)
            return val
        if isinstance(obj, GrynkString):
            try:
                return GrynkString(obj.data[int(raw_key)])
            except IndexError:
                raise GrynkRuntimeError(f"String index {raw_key} out of range", line=line)
        raise GrynkRuntimeError(f"Cannot index into {self._type_name(obj)}", line=line)

    def _eval_Call(self, node, env):
        # Evaluate callee
        callee = self.eval(node.callee, env)
        args = [self.eval(a, env) for a in node.args]
        kwargs = {k: self.eval(v, env) for k, v in node.kwargs.items()}
        return self._call(callee, args, kwargs, node.line)

    def _call(self, callee, args, kwargs, line=None):
        if isinstance(callee, GrynkFunction):
            return self._call_grynk_fn(callee, args, kwargs, line)
        if callable(callee):
            # Check if it wraps a GrynkFunction
            grynk_fn = getattr(callee, '_grynk_fn', None)
            if grynk_fn is not None:
                return self._call_grynk_fn(grynk_fn, args, kwargs, line)
            try:
                return callee(*args, **kwargs)
            except GrynkError:
                raise
            except TypeError as e:
                raise GrynkRuntimeError(f"Argument error: {e}", line=line)
            except Exception as e:
                raise GrynkRuntimeError(str(e), line=line)
        raise GrynkRuntimeError(f"'{grynk_str(callee)}' is not a function", line=line)

    def _call_grynk_fn(self, fn, args, kwargs, line):
        child = Environment(fn.closure_env)
        # Bind params
        for i, (pname, pdefault) in enumerate(fn.params):
            if pname in kwargs:
                child.define(pname, kwargs[pname])
            elif i < len(args):
                child.define(pname, args[i])
            elif pdefault is not None:
                child.define(pname, self.eval(pdefault, fn.closure_env))
            else:
                raise GrynkRuntimeError(
                    f"Missing argument '{pname}' for function '{fn.name}'", line=line
                )
        try:
            self.exec_block(fn.body, child)
            return None
        except ReturnSignal as r:
            return r.value

    def _eval_Lambda(self, node, env):
        fn = GrynkFunction('<lambda>', node.params, node.body, env)
        return self._make_callable(fn)

    def _eval_FnDecl(self, node, env):
        # fn used in expression context (shouldn't normally happen, but handle it)
        fn = GrynkFunction(node.name, node.params, node.body, env)
        env.define(node.name, self._make_callable(fn))
        return None

    def _make_callable(self, fn):
        """Return a Python callable that wraps a GrynkFunction."""
        def _call(*args):
            return self._call_grynk_fn(fn, list(args), {}, None)
        _call._grynk_fn = fn
        return _call

    def _eval_Pipe(self, node, env):
        """left |> right: if right is a Call, prepend left as first arg; else call right(left)"""
        left_val = self.eval(node.left, env)
        right = node.right
        if isinstance(right, Call):
            # Re-evaluate with left inserted at front of args
            callee = self.eval(right.callee, env)
            args = [left_val] + [self.eval(a, env) for a in right.args]
            kwargs = {k: self.eval(v, env) for k, v in right.kwargs.items()}
            return self._call(callee, args, kwargs, node.line)
        else:
            # right is a function expression / ident
            fn = self.eval(right, env)
            return self._call(fn, [left_val], {}, node.line)


def run_source(source, filename='<input>'):
    from .lexer import tokenize
    from .parser import parse

    tokens = tokenize(source, filename)
    ast = parse(tokens, source)
    interp = Interpreter()
    interp.run(ast)
    return interp
