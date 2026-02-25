"""Grynk Parser — recursive-descent parser producing an AST."""

from .lexer import TT, Token
from .errors import GrynkParseError

# ── AST Nodes ─────────────────────────────────────────────────────────────────

class Node:
    """Base AST node."""
    __slots__ = ('line',)
    def __init__(self, line=None):
        self.line = line

class Program(Node):
    __slots__ = ('body', 'line')
    def __init__(self, body, line=None):
        self.body = body
        self.line = line

class VarDecl(Node):
    __slots__ = ('name', 'value', 'mutable', 'line')
    def __init__(self, name, value, mutable, line=None):
        self.name = name; self.value = value; self.mutable = mutable; self.line = line

class Assign(Node):
    __slots__ = ('target', 'value', 'op', 'line')
    def __init__(self, target, value, op='=', line=None):
        self.target = target; self.value = value; self.op = op; self.line = line

class FnDecl(Node):
    __slots__ = ('name', 'params', 'body', 'line')
    def __init__(self, name, params, body, line=None):
        self.name = name; self.params = params; self.body = body; self.line = line

class Return(Node):
    __slots__ = ('value', 'line')
    def __init__(self, value, line=None):
        self.value = value; self.line = line

class Say(Node):
    __slots__ = ('value', 'line')
    def __init__(self, value, line=None):
        self.value = value; self.line = line

class If(Node):
    __slots__ = ('condition', 'then_body', 'elif_clauses', 'else_body', 'line')
    def __init__(self, condition, then_body, elif_clauses, else_body, line=None):
        self.condition = condition; self.then_body = then_body
        self.elif_clauses = elif_clauses; self.else_body = else_body; self.line = line

class Loop(Node):
    __slots__ = ('count', 'body', 'line')
    def __init__(self, count, body, line=None):
        self.count = count; self.body = body; self.line = line

class ForIn(Node):
    __slots__ = ('var', 'iterable', 'body', 'line')
    def __init__(self, var, iterable, body, line=None):
        self.var = var; self.iterable = iterable; self.body = body; self.line = line

class While(Node):
    __slots__ = ('condition', 'body', 'line')
    def __init__(self, condition, body, line=None):
        self.condition = condition; self.body = body; self.line = line

class Break(Node):
    __slots__ = ('line',)
    def __init__(self, line=None): self.line = line

class Continue(Node):
    __slots__ = ('line',)
    def __init__(self, line=None): self.line = line

class TryCatch(Node):
    __slots__ = ('try_body', 'err_name', 'catch_body', 'line')
    def __init__(self, try_body, err_name, catch_body, line=None):
        self.try_body = try_body; self.err_name = err_name
        self.catch_body = catch_body; self.line = line

class Throw(Node):
    __slots__ = ('value', 'line')
    def __init__(self, value, line=None):
        self.value = value; self.line = line

class Match(Node):
    __slots__ = ('subject', 'cases', 'default', 'line')
    def __init__(self, subject, cases, default, line=None):
        self.subject = subject; self.cases = cases; self.default = default; self.line = line

class BinOp(Node):
    __slots__ = ('left', 'op', 'right', 'line')
    def __init__(self, left, op, right, line=None):
        self.left = left; self.op = op; self.right = right; self.line = line

class UnaryOp(Node):
    __slots__ = ('op', 'operand', 'line')
    def __init__(self, op, operand, line=None):
        self.op = op; self.operand = operand; self.line = line

class Literal(Node):
    __slots__ = ('value', 'line')
    def __init__(self, value, line=None):
        self.value = value; self.line = line

class ListLiteral(Node):
    __slots__ = ('elements', 'line')
    def __init__(self, elements, line=None):
        self.elements = elements; self.line = line

class DictLiteral(Node):
    __slots__ = ('pairs', 'line')
    def __init__(self, pairs, line=None):
        self.pairs = pairs; self.line = line

class StringInterp(Node):
    """String with interpolated parts: list of ('lit', str) | ('expr', Node)"""
    __slots__ = ('parts', 'line')
    def __init__(self, parts, line=None):
        self.parts = parts; self.line = line

class Ident(Node):
    __slots__ = ('name', 'line')
    def __init__(self, name, line=None):
        self.name = name; self.line = line

class Call(Node):
    __slots__ = ('callee', 'args', 'kwargs', 'line')
    def __init__(self, callee, args, kwargs=None, line=None):
        self.callee = callee; self.args = args
        self.kwargs = kwargs or {}; self.line = line

class Attr(Node):
    __slots__ = ('obj', 'name', 'line')
    def __init__(self, obj, name, line=None):
        self.obj = obj; self.name = name; self.line = line

class Index(Node):
    __slots__ = ('obj', 'key', 'line')
    def __init__(self, obj, key, line=None):
        self.obj = obj; self.key = key; self.line = line

class Pipe(Node):
    __slots__ = ('left', 'right', 'line')
    def __init__(self, left, right, line=None):
        self.left = left; self.right = right; self.line = line

class Lambda(Node):
    __slots__ = ('params', 'body', 'line')
    def __init__(self, params, body, line=None):
        self.params = params; self.body = body; self.line = line

class ExprStmt(Node):
    __slots__ = ('expr', 'line')
    def __init__(self, expr, line=None):
        self.expr = expr; self.line = line


# ── Parser ────────────────────────────────────────────────────────────────────

class Parser:
    def __init__(self, tokens, source=''):
        self.tokens = tokens
        self.pos = 0
        self.source = source

    def peek(self, offset=0):
        idx = self.pos + offset
        if idx < len(self.tokens):
            return self.tokens[idx]
        return self.tokens[-1]  # EOF

    def current(self):
        return self.peek(0)

    def advance(self):
        tok = self.tokens[self.pos]
        if self.pos < len(self.tokens) - 1:
            self.pos += 1
        return tok

    def check(self, type_, value=None):
        t = self.current()
        if t.type != type_:
            return False
        if value is not None and t.value != value:
            return False
        return True

    def match_tok(self, type_, value=None):
        if self.check(type_, value):
            return self.advance()
        return None

    def expect(self, type_, value=None, msg=None):
        tok = self.match_tok(type_, value)
        if tok is None:
            cur = self.current()
            err_msg = msg or f"Expected {value or type_!r}, got {cur.value!r}"
            raise GrynkParseError(err_msg, line=cur.line)
        return tok

    def skip_newlines(self):
        while self.check(TT.NEWLINE):
            self.advance()

    # ── top-level ──────────────────────────────────────────────────────────────

    def parse(self):
        body = []
        self.skip_newlines()
        while not self.check(TT.EOF):
            stmt = self.parse_statement()
            if stmt is not None:
                body.append(stmt)
            self.skip_newlines()
        return Program(body, line=1)

    def parse_block(self):
        """Parse { statements }"""
        self.expect(TT.LBRACE, msg="Expected '{' to start block")
        self.skip_newlines()
        stmts = []
        while not self.check(TT.RBRACE) and not self.check(TT.EOF):
            stmt = self.parse_statement()
            if stmt is not None:
                stmts.append(stmt)
            self.skip_newlines()
        self.expect(TT.RBRACE, msg="Expected '}' to close block")
        return stmts

    def parse_statement(self):
        tok = self.current()

        # skip bare newlines
        if tok.type == TT.NEWLINE:
            self.advance()
            return None

        # let / mut
        if tok.type == TT.KEYWORD and tok.value in ('let', 'mut'):
            return self.parse_var_decl()

        # fn
        if tok.type == TT.KEYWORD and tok.value == 'fn':
            return self.parse_fn_decl()

        # return
        if tok.type == TT.KEYWORD and tok.value == 'return':
            return self.parse_return()

        # say
        if tok.type == TT.KEYWORD and tok.value == 'say':
            return self.parse_say()

        # if
        if tok.type == TT.KEYWORD and tok.value == 'if':
            return self.parse_if()

        # loop N times
        if tok.type == TT.KEYWORD and tok.value == 'loop':
            return self.parse_loop()

        # for x in list
        if tok.type == TT.KEYWORD and tok.value == 'for':
            return self.parse_for_in()

        # while
        if tok.type == TT.KEYWORD and tok.value == 'while':
            return self.parse_while()

        # break / continue
        if tok.type == TT.KEYWORD and tok.value == 'break':
            self.advance()
            self._end_stmt()
            return Break(line=tok.line)

        if tok.type == TT.KEYWORD and tok.value == 'continue':
            self.advance()
            self._end_stmt()
            return Continue(line=tok.line)

        # try/catch
        if tok.type == TT.KEYWORD and tok.value == 'try':
            return self.parse_try_catch()

        # throw
        if tok.type == TT.KEYWORD and tok.value == 'throw':
            return self.parse_throw()

        # match
        if tok.type == TT.KEYWORD and tok.value == 'match':
            return self.parse_match()

        # expression statement (assignment, call, pipe, etc.)
        return self.parse_expr_stmt()

    def _end_stmt(self):
        """Consume optional newline at end of statement."""
        self.match_tok(TT.NEWLINE)

    def parse_var_decl(self):
        tok = self.advance()
        mutable = tok.value == 'mut'
        line = tok.line
        name = self.expect(TT.IDENT, msg="Expected variable name after let/mut").value
        self.expect(TT.ASSIGN, msg="Expected '=' in variable declaration")
        value = self.parse_expr()
        self._end_stmt()
        return VarDecl(name, value, mutable, line=line)

    def parse_fn_decl(self):
        line = self.current().line
        self.advance()  # consume 'fn'
        name = self.expect(TT.IDENT, msg="Expected function name after 'fn'").value
        self.expect(TT.LPAREN)
        params = self.parse_param_list()
        self.expect(TT.RPAREN)
        body = self.parse_block()
        return FnDecl(name, params, body, line=line)

    def parse_param_list(self):
        """Returns list of (name, default_value_node | None)"""
        params = []
        while not self.check(TT.RPAREN) and not self.check(TT.EOF):
            name = self.expect(TT.IDENT, msg="Expected parameter name").value
            default = None
            if self.match_tok(TT.ASSIGN):
                default = self.parse_expr()
            params.append((name, default))
            if not self.match_tok(TT.COMMA):
                break
        return params

    def parse_return(self):
        line = self.current().line
        self.advance()
        if self.check(TT.NEWLINE) or self.check(TT.RBRACE) or self.check(TT.EOF):
            self._end_stmt()
            return Return(None, line=line)
        value = self.parse_expr()
        self._end_stmt()
        return Return(value, line=line)

    def parse_say(self):
        line = self.current().line
        self.advance()
        value = self.parse_expr()
        self._end_stmt()
        return Say(value, line=line)

    def parse_if(self):
        line = self.current().line
        self.advance()  # consume 'if'
        condition = self.parse_expr()
        then_body = self.parse_block()
        elif_clauses = []
        else_body = None
        self.skip_newlines()
        while self.check(TT.KEYWORD, 'elif'):
            self.advance()
            elif_cond = self.parse_expr()
            elif_body = self.parse_block()
            elif_clauses.append((elif_cond, elif_body))
            self.skip_newlines()
        if self.check(TT.KEYWORD, 'else'):
            self.advance()
            else_body = self.parse_block()
        return If(condition, then_body, elif_clauses, else_body, line=line)

    def parse_loop(self):
        line = self.current().line
        self.advance()  # consume 'loop'
        count = self.parse_expr()
        self.expect(TT.KEYWORD, 'times', msg="Expected 'times' after loop count")
        body = self.parse_block()
        return Loop(count, body, line=line)

    def parse_for_in(self):
        line = self.current().line
        self.advance()  # consume 'for'
        var = self.expect(TT.IDENT, msg="Expected variable name in for loop").value
        self.expect(TT.KEYWORD, 'in', msg="Expected 'in' in for loop")
        iterable = self.parse_expr()
        body = self.parse_block()
        return ForIn(var, iterable, body, line=line)

    def parse_while(self):
        line = self.current().line
        self.advance()
        condition = self.parse_expr()
        body = self.parse_block()
        return While(condition, body, line=line)

    def parse_try_catch(self):
        line = self.current().line
        self.advance()  # 'try'
        try_body = self.parse_block()
        self.skip_newlines()
        self.expect(TT.KEYWORD, 'catch', msg="Expected 'catch' after try block")
        err_name = None
        if self.check(TT.LPAREN):
            self.advance()
            err_name = self.expect(TT.IDENT).value
            self.expect(TT.RPAREN)
        catch_body = self.parse_block()
        return TryCatch(try_body, err_name, catch_body, line=line)

    def parse_throw(self):
        line = self.current().line
        self.advance()
        value = self.parse_expr()
        self._end_stmt()
        return Throw(value, line=line)

    def parse_match(self):
        line = self.current().line
        self.advance()  # 'match'
        subject = self.parse_expr()
        self.expect(TT.LBRACE)
        self.skip_newlines()
        cases = []
        default = None
        while not self.check(TT.RBRACE) and not self.check(TT.EOF):
            if self.check(TT.KEYWORD, 'case'):
                self.advance()
                if self.check(TT.IDENT) and self.current().value == '_':
                    self.advance()
                    case_body = self.parse_block()
                    default = case_body
                else:
                    case_val = self.parse_expr()
                    case_body = self.parse_block()
                    cases.append((case_val, case_body))
            else:
                break
            self.skip_newlines()
        self.expect(TT.RBRACE)
        return Match(subject, cases, default, line=line)

    def parse_expr_stmt(self):
        line = self.current().line
        expr = self.parse_expr()
        # Check for assignment (augmented or plain) on ident or attr/index
        if self.check(TT.ASSIGN):
            self.advance()
            value = self.parse_expr()
            self._end_stmt()
            return Assign(expr, value, '=', line=line)
        if self.check(TT.PLUS_ASSIGN):
            self.advance()
            value = self.parse_expr()
            self._end_stmt()
            return Assign(expr, value, '+=', line=line)
        if self.check(TT.MINUS_ASSIGN):
            self.advance()
            value = self.parse_expr()
            self._end_stmt()
            return Assign(expr, value, '-=', line=line)
        self._end_stmt()
        return ExprStmt(expr, line=line)

    # ── expressions (precedence climbing) ────────────────────────────────────

    def parse_expr(self):
        return self.parse_pipe()

    def parse_pipe(self):
        left = self.parse_or()
        while self.check(TT.PIPE):
            line = self.current().line
            self.advance()
            right = self.parse_or()
            left = Pipe(left, right, line=line)
        return left

    def parse_or(self):
        left = self.parse_and()
        while self.check(TT.OR):
            line = self.current().line
            op = self.advance().value
            right = self.parse_and()
            left = BinOp(left, 'or', right, line=line)
        return left

    def parse_and(self):
        left = self.parse_not()
        while self.check(TT.AND):
            line = self.current().line
            op = self.advance().value
            right = self.parse_not()
            left = BinOp(left, 'and', right, line=line)
        return left

    def parse_not(self):
        if self.check(TT.NOT):
            line = self.current().line
            self.advance()
            operand = self.parse_not()
            return UnaryOp('not', operand, line=line)
        return self.parse_comparison()

    def parse_comparison(self):
        left = self.parse_add()
        cmp_ops = {TT.EQ: '==', TT.NEQ: '!=', TT.LT: '<',
                   TT.GT: '>', TT.LTE: '<=', TT.GTE: '>='}
        while self.current().type in cmp_ops:
            line = self.current().line
            op = cmp_ops[self.advance().type]
            right = self.parse_add()
            left = BinOp(left, op, right, line=line)
        return left

    def parse_add(self):
        left = self.parse_mul()
        while self.current().type in (TT.PLUS, TT.MINUS):
            line = self.current().line
            op = self.advance().value
            right = self.parse_mul()
            left = BinOp(left, op, right, line=line)
        return left

    def parse_mul(self):
        left = self.parse_power()
        while self.current().type in (TT.STAR, TT.SLASH, TT.PERCENT):
            line = self.current().line
            op = self.advance().value
            right = self.parse_power()
            left = BinOp(left, op, right, line=line)
        return left

    def parse_power(self):
        base = self.parse_unary()
        if self.check(TT.POWER):
            line = self.current().line
            self.advance()
            exp = self.parse_power()  # right-associative
            return BinOp(base, '**', exp, line=line)
        return base

    def parse_unary(self):
        if self.check(TT.MINUS):
            line = self.current().line
            self.advance()
            operand = self.parse_unary()
            return UnaryOp('-', operand, line=line)
        if self.check(TT.NOT):
            line = self.current().line
            self.advance()
            operand = self.parse_unary()
            return UnaryOp('not', operand, line=line)
        return self.parse_postfix()

    def parse_postfix(self):
        node = self.parse_primary()
        while True:
            if self.check(TT.DOT):
                line = self.current().line
                self.advance()
                attr_name = self.expect(TT.IDENT, msg="Expected attribute name after '.'").value
                if self.check(TT.LPAREN):
                    # method call
                    self.advance()
                    args, kwargs = self.parse_arg_list()
                    self.expect(TT.RPAREN)
                    callee = Attr(node, attr_name, line=line)
                    node = Call(callee, args, kwargs, line=line)
                else:
                    node = Attr(node, attr_name, line=line)
            elif self.check(TT.LBRACKET):
                line = self.current().line
                self.advance()
                key = self.parse_expr()
                self.expect(TT.RBRACKET)
                node = Index(node, key, line=line)
            elif self.check(TT.LPAREN):
                line = self.current().line
                self.advance()
                args, kwargs = self.parse_arg_list()
                self.expect(TT.RPAREN)
                node = Call(node, args, kwargs, line=line)
            else:
                break
        return node

    def parse_primary(self):
        tok = self.current()

        # Literals
        if tok.type == TT.INT:
            self.advance()
            return Literal(tok.value, line=tok.line)
        if tok.type == TT.FLOAT:
            self.advance()
            return Literal(tok.value, line=tok.line)
        if tok.type == TT.BOOL:
            self.advance()
            return Literal(tok.value, line=tok.line)
        if tok.type == TT.NULL:
            self.advance()
            return Literal(None, line=tok.line)

        # String (possibly with interpolation)
        if tok.type == TT.STRING:
            self.advance()
            parts = tok.value  # list of ('lit', s) | ('interp', code_str)
            if all(kind == 'lit' for kind, _ in parts):
                # plain string
                return Literal(''.join(s for _, s in parts), line=tok.line)
            # interpolated string — parse each interp expression
            parsed_parts = []
            for kind, val in parts:
                if kind == 'lit':
                    parsed_parts.append(('lit', val))
                else:
                    sub_tokens = self._lex_fragment(val, tok.line)
                    sub_ast = Parser(sub_tokens).parse_expr()
                    parsed_parts.append(('expr', sub_ast))
            return StringInterp(parsed_parts, line=tok.line)

        # List literal
        if tok.type == TT.LBRACKET:
            line = tok.line
            self.advance()
            elements = []
            self.skip_newlines()
            while not self.check(TT.RBRACKET) and not self.check(TT.EOF):
                elements.append(self.parse_expr())
                self.skip_newlines()
                if not self.match_tok(TT.COMMA):
                    break
                self.skip_newlines()
            self.expect(TT.RBRACKET)
            return ListLiteral(elements, line=line)

        # Dict literal  { key: val, ... }  — but ALSO block starting char!
        # We detect dict literal by: { followed by expr, then ':'
        if tok.type == TT.LBRACE:
            return self.parse_dict_or_block()

        # Parenthesised expression
        if tok.type == TT.LPAREN:
            line = tok.line
            self.advance()
            node = self.parse_expr()
            self.expect(TT.RPAREN)
            return node

        # Lambda/closure:  fn(params) { body }  inside expression position
        if tok.type == TT.KEYWORD and tok.value == 'fn':
            return self.parse_lambda()

        # Identifier
        if tok.type == TT.IDENT:
            self.advance()
            return Ident(tok.value, line=tok.line)

        # ask() built-in keyword used as expression
        if tok.type == TT.KEYWORD and tok.value == 'ask':
            line = tok.line
            self.advance()
            self.expect(TT.LPAREN)
            args, kwargs = self.parse_arg_list()
            self.expect(TT.RPAREN)
            return Call(Ident('ask', line=line), args, kwargs, line=line)

        raise GrynkParseError(
            f"Unexpected token '{tok.value}' in expression",
            line=tok.line
        )

    def parse_dict_or_block(self):
        """Heuristic: if we see { expr : ... it's a dict literal."""
        line = self.current().line
        self.advance()  # consume {
        self.skip_newlines()
        # empty dict
        if self.check(TT.RBRACE):
            self.advance()
            return DictLiteral([], line=line)
        
        # Check for first key: val
        save_pos = self.pos
        try:
            key = self.parse_expr()
            self.expect(TT.COLON, msg="Expected ':' after key in dict literal")
            val = self.parse_expr()
            pairs = [(key, val)]
            self.skip_newlines()
            while self.match_tok(TT.COMMA):
                self.skip_newlines()
                if self.check(TT.RBRACE):
                    break
                k = self.parse_expr()
                self.expect(TT.COLON, msg="Expected ':' after key in dict literal")
                v = self.parse_expr()
                pairs.append((k, v))
                self.skip_newlines()
            self.expect(TT.RBRACE, msg="Expected '}' to close dict literal")
            return DictLiteral(pairs, line=line)
        except GrynkParseError as e:
            # If we already passed the colon, it's definitely a dict, so re-raise
            if self.pos > save_pos + 1:
                raise e
            
            # Otherwise, backtrack and give the generic error
            self.pos = save_pos
            raise GrynkParseError(
                f"Unexpected '{{' in expression context (did you mean to use a dict? {e.message})",
                line=line
            )

    def parse_lambda(self):
        line = self.current().line
        self.advance()  # fn
        self.expect(TT.LPAREN)
        params = self.parse_param_list()
        self.expect(TT.RPAREN)
        body = self.parse_block()
        return Lambda(params, body, line=line)

    def parse_arg_list(self):
        """Returns (positional_args, kwargs_dict)."""
        args = []
        kwargs = {}
        self.skip_newlines()
        while not self.check(TT.RPAREN) and not self.check(TT.EOF):
            # keyword argument: ident = expr
            if self.check(TT.IDENT) and self.peek(1).type == TT.ASSIGN:
                name = self.advance().value
                self.advance()  # =
                val = self.parse_expr()
                kwargs[name] = val
            else:
                args.append(self.parse_expr())
            self.skip_newlines()
            if not self.match_tok(TT.COMMA):
                break
            self.skip_newlines()
        return args, kwargs

    def _lex_fragment(self, code, base_line):
        """Lex a small code fragment (used for string interpolation)."""
        from .lexer import Lexer
        return Lexer(code).tokenize()


def parse(tokens, source=''):
    return Parser(tokens, source).parse()
