from __future__ import annotations

import math
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any


class KDLParseError(ValueError):
    def __init__(self, message: str, *, line: int, column: int, offset: int):
        super().__init__(f"{message} at {line}:{column} (offset={offset})")
        self.message = message
        self.line = line
        self.column = column
        self.offset = offset


@dataclass(frozen=True)
class Position:
    offset: int
    line: int
    column: int


@dataclass(frozen=True)
class Span:
    start: Position
    end: Position


class TokenType(str, Enum):
    IDENT = "IDENT"
    STRING = "STRING"
    NUMBER = "NUMBER"
    BOOL = "BOOL"
    NULL = "NULL"
    KEYWORD_NUMBER = "KEYWORD_NUMBER"
    LBRACE = "LBRACE"
    RBRACE = "RBRACE"
    LPAREN = "LPAREN"
    RPAREN = "RPAREN"
    EQUAL = "EQUAL"
    SEMI = "SEMI"
    NEWLINE = "NEWLINE"
    SLASHDASH = "SLASHDASH"
    EOF = "EOF"


@dataclass(frozen=True)
class Token:
    typ: TokenType
    raw: str
    value: Any
    span: Span


@dataclass(frozen=True)
class CSTTypeAnnotation:
    raw: str
    span: Span


@dataclass(frozen=True)
class CSTIdentifier:
    value: str
    raw: str
    span: Span


@dataclass(frozen=True)
class CSTValue:
    value: Any
    raw: str
    span: Span
    type_annotation: CSTTypeAnnotation | None = None


@dataclass(frozen=True)
class CSTArgEntry:
    value: CSTValue | CSTIdentifier
    span: Span


@dataclass(frozen=True)
class CSTPropEntry:
    key: CSTIdentifier
    value: CSTValue | CSTIdentifier
    span: Span


CSTEntry = CSTArgEntry | CSTPropEntry


@dataclass(frozen=True)
class CSTNode:
    name: CSTIdentifier
    type_annotation: CSTTypeAnnotation | None
    entries: list[CSTEntry]
    children: list["CSTNode"]
    span: Span


@dataclass(frozen=True)
class CSTDocument:
    nodes: list[CSTNode]
    span: Span


_DECIMAL_RE = re.compile(
    r"[+-]?[0-9][0-9_]*(?:\.[0-9][0-9_]*)?(?:[eE][+-]?[0-9][0-9_]*)?"
)
_HEX_RE = re.compile(r"[+-]?0x[0-9a-fA-F][0-9a-fA-F_]*")
_OCT_RE = re.compile(r"[+-]?0o[0-7][0-7_]*")
_BIN_RE = re.compile(r"[+-]?0b[01][01_]*")


# KDL newline set (CRLF treated as single newline)
_NEWLINES = {"\n", "\r", "\u0085", "\u000b", "\u000c", "\u2028", "\u2029"}

# KDL unicode-space (excluding newlines)
_UNICODE_SPACES = {
    "\u0009",
    "\u0020",
    "\u00A0",
    "\u1680",
    "\u2000",
    "\u2001",
    "\u2002",
    "\u2003",
    "\u2004",
    "\u2005",
    "\u2006",
    "\u2007",
    "\u2008",
    "\u2009",
    "\u200A",
    "\u202F",
    "\u205F",
    "\u3000",
}

_DISALLOWED_IDENT_CHARS = set('\\/(){};[]"=#')
_RESERVED_BARE_IDENTS = {"true", "false", "null", "inf", "-inf", "nan"}


@dataclass
class _Cursor:
    src: str
    i: int = 0
    line: int = 1
    col: int = 1

    def eof(self) -> bool:
        return self.i >= len(self.src)

    def cur(self) -> str:
        if self.eof():
            return ""
        return self.src[self.i]

    def peek(self, n: int = 1) -> str:
        j = self.i + n
        if j >= len(self.src):
            return ""
        return self.src[j]

    def startswith(self, s: str) -> bool:
        return self.src.startswith(s, self.i)

    def pos(self) -> Position:
        return Position(offset=self.i, line=self.line, column=self.col)

    def advance(self, n: int = 1) -> str:
        out = []
        for _ in range(n):
            if self.eof():
                break
            ch = self.src[self.i]
            out.append(ch)
            self.i += 1
            if ch in _NEWLINES:
                self.line += 1
                self.col = 1
            else:
                self.col += 1
        return "".join(out)


class KDLLexer:
    def __init__(self, source: str):
        self.c = _Cursor(source)

    def tokenize(self) -> list[Token]:
        tokens: list[Token] = []
        while not self.c.eof():
            self._check_disallowed_literal()
            ch = self.c.cur()

            if self.c.startswith("\r\n"):
                tokens.append(self._consume_newline_pair())
                continue

            if ch in _NEWLINES:
                tokens.append(self._consume_newline_single())
                continue

            if ch in _UNICODE_SPACES:
                self.c.advance()
                continue

            if self.c.startswith("\\"):
                if self._try_consume_escline():
                    continue

            if self.c.startswith("//"):
                self._consume_line_comment()
                continue

            if self.c.startswith("/*"):
                self._consume_block_comment()
                continue

            if self.c.startswith("/-"):
                tokens.append(self._single(TokenType.SLASHDASH, 2))
                continue

            if ch == "{":
                tokens.append(self._single(TokenType.LBRACE))
                continue
            if ch == "}":
                tokens.append(self._single(TokenType.RBRACE))
                continue
            if ch == "(":
                tokens.append(self._single(TokenType.LPAREN))
                continue
            if ch == ")":
                tokens.append(self._single(TokenType.RPAREN))
                continue
            if ch == "=":
                tokens.append(self._single(TokenType.EQUAL))
                continue
            if ch == ";":
                tokens.append(self._single(TokenType.SEMI))
                continue

            if ch == '"':
                tokens.append(self._read_quoted_or_multiline_string())
                continue

            if ch == "#":
                tok = self._read_hash_prefixed()
                if tok is not None:
                    tokens.append(tok)
                    continue

            tok = self._try_read_number()
            if tok is not None:
                tokens.append(tok)
                continue

            if self._can_start_ident(ch):
                tokens.append(self._read_identifier())
                continue

            pos = self.c.pos()
            raise KDLParseError(
                f"Unexpected character {ch!r}",
                line=pos.line,
                column=pos.column,
                offset=pos.offset,
            )

        eof = self.c.pos()
        tokens.append(Token(TokenType.EOF, "", None, Span(eof, eof)))
        return tokens

    def _check_disallowed_literal(self) -> None:
        ch = self.c.cur()
        cp = ord(ch)

        # U+FEFF only allowed at first code point in document.
        if cp == 0xFEFF and self.c.i != 0:
            pos = self.c.pos()
            raise KDLParseError(
                "Disallowed literal BOM U+FEFF outside document start",
                line=pos.line,
                column=pos.column,
                offset=pos.offset,
            )

        if 0xD800 <= cp <= 0xDFFF:
            pos = self.c.pos()
            raise KDLParseError(
                "Disallowed surrogate code point",
                line=pos.line,
                column=pos.column,
                offset=pos.offset,
            )

        if (0x0000 <= cp <= 0x0008) or (0x000E <= cp <= 0x001F) or cp == 0x007F:
            pos = self.c.pos()
            raise KDLParseError(
                f"Disallowed control code point U+{cp:04X}",
                line=pos.line,
                column=pos.column,
                offset=pos.offset,
            )

        if (0x200E <= cp <= 0x200F) or (0x202A <= cp <= 0x202E) or (0x2066 <= cp <= 0x2069):
            pos = self.c.pos()
            raise KDLParseError(
                f"Disallowed direction-control code point U+{cp:04X}",
                line=pos.line,
                column=pos.column,
                offset=pos.offset,
            )

    def _single(self, typ: TokenType, n: int = 1) -> Token:
        start = self.c.pos()
        raw = self.c.advance(n)
        return Token(typ=typ, raw=raw, value=raw, span=Span(start, self.c.pos()))

    def _consume_newline_pair(self) -> Token:
        start = self.c.pos()
        raw = self.c.advance(2)
        return Token(TokenType.NEWLINE, raw, "\n", Span(start, self.c.pos()))

    def _consume_newline_single(self) -> Token:
        start = self.c.pos()
        raw = self.c.advance()
        return Token(TokenType.NEWLINE, raw, "\n", Span(start, self.c.pos()))

    def _try_consume_escline(self) -> bool:
        # escline := '\\' ws* (single-line-comment | newline | eof)
        start_i = self.c.i
        start = self.c.pos()
        self.c.advance()  # backslash

        while not self.c.eof() and self.c.cur() in _UNICODE_SPACES:
            self.c.advance()

        if self.c.startswith("//"):
            self._consume_line_comment()

        if self.c.eof():
            return True

        if self.c.startswith("\r\n"):
            self.c.advance(2)
            return True

        if self.c.cur() in _NEWLINES:
            self.c.advance()
            return True

        # Not an escline, revert.
        self.c.i = start_i
        self.c.line = start.line
        self.c.col = start.column
        return False

    def _consume_line_comment(self) -> None:
        self.c.advance(2)
        while not self.c.eof():
            if self.c.startswith("\r\n"):
                break
            if self.c.cur() in _NEWLINES:
                break
            self.c.advance()

    def _consume_block_comment(self) -> None:
        start = self.c.pos()
        self.c.advance(2)
        depth = 1
        while not self.c.eof():
            if self.c.startswith("/*"):
                depth += 1
                self.c.advance(2)
                continue
            if self.c.startswith("*/"):
                depth -= 1
                self.c.advance(2)
                if depth == 0:
                    return
                continue
            if self.c.startswith("\r\n"):
                self.c.advance(2)
                continue
            self.c.advance()

        raise KDLParseError(
            "Unterminated block comment",
            line=start.line,
            column=start.column,
            offset=start.offset,
        )

    def _read_quoted_or_multiline_string(self) -> Token:
        start = self.c.pos()

        if self.c.startswith('"""'):
            self.c.advance(3)
            content_start = self.c.i
            while not self.c.eof():
                if self.c.startswith('"""'):
                    content = self.c.src[content_start : self.c.i]
                    self.c.advance(3)
                    raw = self.c.src[start.offset : self.c.i]
                    return Token(TokenType.STRING, raw, _decode_multiline(content), Span(start, self.c.pos()))
                if self.c.startswith("\\") and self._try_consume_escline():
                    continue
                if self.c.startswith("\r\n"):
                    self.c.advance(2)
                    continue
                self.c.advance()
            raise KDLParseError(
                "Unterminated multiline string",
                line=start.line,
                column=start.column,
                offset=start.offset,
            )

        # single-line quoted string
        self.c.advance()
        escaped = False
        while not self.c.eof():
            if self.c.startswith("\r\n"):
                pos = self.c.pos()
                raise KDLParseError(
                    "Newline in quoted string",
                    line=pos.line,
                    column=pos.column,
                    offset=pos.offset,
                )
            ch = self.c.cur()
            if ch in _NEWLINES:
                pos = self.c.pos()
                raise KDLParseError(
                    "Newline in quoted string",
                    line=pos.line,
                    column=pos.column,
                    offset=pos.offset,
                )
            if escaped:
                escaped = False
                self.c.advance()
                continue
            if ch == "\\":
                escaped = True
                self.c.advance()
                continue
            if ch == '"':
                self.c.advance()
                raw = self.c.src[start.offset : self.c.i]
                return Token(TokenType.STRING, raw, _decode_quoted(raw), Span(start, self.c.pos()))
            self.c.advance()

        raise KDLParseError(
            "Unterminated quoted string",
            line=start.line,
            column=start.column,
            offset=start.offset,
        )

    def _read_hash_prefixed(self) -> Token | None:
        start = self.c.pos()

        if self.c.startswith("#true") and not _is_ident_continue(self.c.peek(5)):
            self.c.advance(5)
            return Token(TokenType.BOOL, "#true", True, Span(start, self.c.pos()))
        if self.c.startswith("#false") and not _is_ident_continue(self.c.peek(6)):
            self.c.advance(6)
            return Token(TokenType.BOOL, "#false", False, Span(start, self.c.pos()))
        if self.c.startswith("#null") and not _is_ident_continue(self.c.peek(5)):
            self.c.advance(5)
            return Token(TokenType.NULL, "#null", None, Span(start, self.c.pos()))

        if self.c.startswith("#inf") and not _is_ident_continue(self.c.peek(4)):
            self.c.advance(4)
            return Token(TokenType.KEYWORD_NUMBER, "#inf", math.inf, Span(start, self.c.pos()))
        if self.c.startswith("#-inf") and not _is_ident_continue(self.c.peek(5)):
            self.c.advance(5)
            return Token(TokenType.KEYWORD_NUMBER, "#-inf", -math.inf, Span(start, self.c.pos()))
        if self.c.startswith("#nan") and not _is_ident_continue(self.c.peek(4)):
            self.c.advance(4)
            return Token(TokenType.KEYWORD_NUMBER, "#nan", math.nan, Span(start, self.c.pos()))

        # raw string: #"..."#, ##"..."##, #"""..."""#
        j = self.c.i
        hashes = 0
        while j < len(self.c.src) and self.c.src[j] == "#":
            hashes += 1
            j += 1

        if j >= len(self.c.src) or self.c.src[j] != '"':
            return None

        qlen = 3 if self.c.src.startswith('"""', j) else 1
        opening = "#" * hashes + ('"""' if qlen == 3 else '"')
        closing = ('"""' if qlen == 3 else '"') + ("#" * hashes)

        self.c.advance(len(opening))
        content_start = self.c.i

        while not self.c.eof():
            if self.c.startswith(closing):
                content = self.c.src[content_start : self.c.i]
                self.c.advance(len(closing))
                raw = self.c.src[start.offset : self.c.i]
                value = _decode_multiline(content) if qlen == 3 else content
                return Token(TokenType.STRING, raw, value, Span(start, self.c.pos()))

            if self.c.startswith("\r\n"):
                self.c.advance(2)
                continue
            self.c.advance()

        raise KDLParseError(
            "Unterminated raw string",
            line=start.line,
            column=start.column,
            offset=start.offset,
        )

    def _try_read_number(self) -> Token | None:
        rem = self.c.src[self.c.i :]

        # Prefer radix numbers before decimal.
        for typ, rx, base in (
            (TokenType.NUMBER, _HEX_RE, 16),
            (TokenType.NUMBER, _OCT_RE, 8),
            (TokenType.NUMBER, _BIN_RE, 2),
        ):
            m = rx.match(rem)
            if m:
                raw = m.group(0)
                value = _parse_int_like(raw, base)
                start = self.c.pos()
                self.c.advance(len(raw))
                return Token(typ, raw, value, Span(start, self.c.pos()))

        m = _DECIMAL_RE.match(rem)
        if m:
            raw = m.group(0)
            start = self.c.pos()
            self.c.advance(len(raw))
            norm = raw.replace("_", "")
            value: int | float
            if "." in norm or "e" in norm or "E" in norm:
                value = float(norm)
            else:
                value = int(norm)
            return Token(TokenType.NUMBER, raw, value, Span(start, self.c.pos()))

        return None

    def _can_start_ident(self, ch: str) -> bool:
        if not ch:
            return False
        if ch in _DISALLOWED_IDENT_CHARS:
            return False
        if ch in _UNICODE_SPACES or ch in _NEWLINES:
            return False

        # Disallow starting patterns that look like numbers.
        if ch.isdigit():
            return False
        if ch in "+-":
            n1 = self.c.peek()
            n2 = self.c.peek(2)
            if n1.isdigit():
                return False
            if n1 == "." and n2.isdigit():
                return False
        if ch == "." and self.c.peek().isdigit():
            return False
        return True

    def _read_identifier(self) -> Token:
        start = self.c.pos()
        self.c.advance()
        while not self.c.eof() and _is_ident_continue(self.c.cur()):
            self.c.advance()

        raw = self.c.src[start.offset : self.c.i]
        if raw in _RESERVED_BARE_IDENTS:
            raise KDLParseError(
                f"Reserved bare identifier {raw!r}",
                line=start.line,
                column=start.column,
                offset=start.offset,
            )

        return Token(TokenType.IDENT, raw, raw, Span(start, self.c.pos()))


class KDL2CSTParser:
    def parse(self, source: str) -> CSTDocument:
        tokens = KDLLexer(source).tokenize()
        p = _Parser(tokens)
        return p.parse_document()


class _Parser:
    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.i = 0

    def parse_document(self) -> CSTDocument:
        nodes: list[CSTNode] = []
        self._skip_separators()
        start = self._peek().span.start

        while not self._at(TokenType.EOF):
            if self._match(TokenType.SLASHDASH):
                self._skip_separators()
                self._parse_discarded_component(allow_node=True)
                self._skip_separators()
                continue

            nodes.append(self._parse_node())
            self._consume_terminators()
            self._skip_separators()

        end = self._peek().span.end
        return CSTDocument(nodes=nodes, span=Span(start, end))

    def _parse_discarded_component(self, *, allow_node: bool) -> None:
        # Slashdash can drop node / argument / property / children block.
        # We parse and discard exactly one component.
        if self._at(TokenType.LBRACE):
            self._discard_children_block()
            return

        if allow_node:
            save = self.i
            try:
                self._parse_node()
                return
            except Exception:
                self.i = save

        # property or argument
        self._parse_entry()

    def _discard_children_block(self) -> None:
        self._expect(TokenType.LBRACE)
        depth = 1
        while depth > 0:
            tok = self._peek()
            if tok.typ == TokenType.EOF:
                raise KDLParseError(
                    "Unterminated children block",
                    line=tok.span.start.line,
                    column=tok.span.start.column,
                    offset=tok.span.start.offset,
                )
            if tok.typ == TokenType.LBRACE:
                depth += 1
            elif tok.typ == TokenType.RBRACE:
                depth -= 1
            self._advance()

    def _parse_node(self) -> CSTNode:
        node_type = self._try_parse_type_annotation()
        name = self._parse_identifier_like()

        entries: list[CSTEntry] = []
        children: list[CSTNode] = []

        while not self._is_node_terminator() and not self._at(TokenType.LBRACE):
            if self._match(TokenType.SLASHDASH):
                self._skip_separators()
                self._parse_discarded_component(allow_node=False)
                self._skip_separators()
                continue
            entries.append(self._parse_entry())

        while True:
            if self._match(TokenType.SLASHDASH):
                self._skip_separators()
                if self._at(TokenType.LBRACE):
                    self._discard_children_block()
                    self._skip_separators()
                    continue
                raise self._error_here("Slashdash in node tail must precede children block")

            if not self._match(TokenType.LBRACE):
                break

            self._skip_separators()
            while not self._at(TokenType.RBRACE):
                if self._match(TokenType.SLASHDASH):
                    self._skip_separators()
                    self._parse_discarded_component(allow_node=True)
                    self._skip_separators()
                    continue

                if self._at(TokenType.EOF):
                    raise self._error_here("Unterminated children block")
                children.append(self._parse_node())
                self._consume_terminators()
                self._skip_separators()
            self._expect(TokenType.RBRACE)
            self._skip_separators()

        end = (
            self._prev().span.end
            if self.i > 0
            else name.span.end
        )
        return CSTNode(
            name=name,
            type_annotation=node_type,
            entries=entries,
            children=children,
            span=Span((node_type.span.start if node_type else name.span.start), end),
        )

    def _parse_entry(self) -> CSTEntry:
        # property: key = value, where key is an identifier string
        if self._is_identifier_token(self._peek()) and self._peek(1).typ == TokenType.EQUAL:
            key = self._parse_identifier_like()
            self._expect(TokenType.EQUAL)
            value = self._parse_value_like()
            return CSTPropEntry(key=key, value=value, span=Span(key.span.start, value.span.end))

        value = self._parse_value_like()
        return CSTArgEntry(value=value, span=value.span)

    def _try_parse_type_annotation(self) -> CSTTypeAnnotation | None:
        if not self._match(TokenType.LPAREN):
            return None

        l = self._prev()
        ident = self._parse_identifier_like()
        r = self._expect(TokenType.RPAREN)

        raw = self._slice(l.span.start.offset, r.span.end.offset)
        return CSTTypeAnnotation(raw=raw, span=Span(l.span.start, r.span.end))

    def _parse_identifier_like(self) -> CSTIdentifier:
        tok = self._peek()
        if not self._is_identifier_token(tok):
            raise self._error_tok(tok, f"Expected identifier, got {tok.typ}")
        self._advance()
        return CSTIdentifier(value=str(tok.value), raw=tok.raw, span=tok.span)

    def _parse_value_like(self) -> CSTValue | CSTIdentifier:
        ty = self._try_parse_type_annotation()
        tok = self._peek()

        if tok.typ in (TokenType.STRING, TokenType.NUMBER, TokenType.BOOL, TokenType.NULL, TokenType.KEYWORD_NUMBER):
            self._advance()
            start = ty.span.start if ty else tok.span.start
            raw = self._slice(start.offset, tok.span.end.offset)
            return CSTValue(value=tok.value, raw=raw, span=Span(start, tok.span.end), type_annotation=ty)

        if tok.typ == TokenType.IDENT:
            self._advance()
            if ty:
                # typed value with bare identifier string is still a string value
                raw = self._slice(ty.span.start.offset, tok.span.end.offset)
                return CSTValue(value=str(tok.value), raw=raw, span=Span(ty.span.start, tok.span.end), type_annotation=ty)
            return CSTIdentifier(value=str(tok.value), raw=tok.raw, span=tok.span)

        raise self._error_tok(tok, f"Expected value, got {tok.typ}")

    def _is_node_terminator(self) -> bool:
        return self._at(TokenType.NEWLINE) or self._at(TokenType.SEMI) or self._at(TokenType.RBRACE) or self._at(TokenType.EOF)

    def _consume_terminators(self) -> None:
        while self._match(TokenType.NEWLINE) or self._match(TokenType.SEMI):
            pass

    def _skip_separators(self) -> None:
        while self._at(TokenType.NEWLINE) or self._at(TokenType.SEMI):
            self._advance()

    def _is_identifier_token(self, tok: Token) -> bool:
        return tok.typ in (TokenType.IDENT, TokenType.STRING)

    def _slice(self, start: int, end: int) -> str:
        # reconstruct from token raws for stable representation
        out: list[str] = []
        for t in self.tokens:
            if t.span.end.offset <= start:
                continue
            if t.span.start.offset >= end:
                break
            out.append(t.raw)
        return "".join(out)

    def _at(self, typ: TokenType) -> bool:
        return self._peek().typ == typ

    def _match(self, typ: TokenType) -> bool:
        if self._at(typ):
            self._advance()
            return True
        return False

    def _expect(self, typ: TokenType) -> Token:
        tok = self._peek()
        if tok.typ != typ:
            raise self._error_tok(tok, f"Expected {typ}, got {tok.typ}")
        return self._advance()

    def _advance(self) -> Token:
        tok = self.tokens[self.i]
        self.i += 1
        return tok

    def _peek(self, n: int = 0) -> Token:
        idx = self.i + n
        if idx >= len(self.tokens):
            return self.tokens[-1]
        return self.tokens[idx]

    def _prev(self) -> Token:
        if self.i == 0:
            return self.tokens[0]
        return self.tokens[self.i - 1]

    def _error_tok(self, tok: Token, message: str) -> KDLParseError:
        return KDLParseError(
            message,
            line=tok.span.start.line,
            column=tok.span.start.column,
            offset=tok.span.start.offset,
        )

    def _error_here(self, message: str) -> KDLParseError:
        return self._error_tok(self._peek(), message)


def _parse_int_like(raw: str, base: int) -> int:
    sign = 1
    s = raw
    if s[0] == "+":
        s = s[1:]
    elif s[0] == "-":
        sign = -1
        s = s[1:]

    if base == 16:
        s = s[2:]
    elif base == 8:
        s = s[2:]
    elif base == 2:
        s = s[2:]
    return sign * int(s.replace("_", ""), base)


def _decode_quoted(raw: str) -> str:
    body = raw[1:-1]
    out: list[str] = []
    i = 0

    while i < len(body):
        ch = body[i]
        if ch != "\\":
            out.append(ch)
            i += 1
            continue

        i += 1
        if i >= len(body):
            out.append("\\")
            break

        esc = body[i]
        if esc == "n":
            out.append("\n")
        elif esc == "r":
            out.append("\r")
        elif esc == "t":
            out.append("\t")
        elif esc == "b":
            out.append("\b")
        elif esc == "f":
            out.append("\f")
        elif esc == "\\":
            out.append("\\")
        elif esc == "/":
            out.append("/")
        elif esc == '"':
            out.append('"')
        elif esc == "u" and i + 1 < len(body) and body[i + 1] == "{":
            end = body.find("}", i + 2)
            if end == -1:
                out.append("\\u")
            else:
                hex_part = body[i + 2 : end]
                if 1 <= len(hex_part) <= 6 and all(c in "0123456789abcdefABCDEF" for c in hex_part):
                    cp = int(hex_part, 16)
                    out.append(chr(cp))
                    i = end
                else:
                    out.append("\\u{" + hex_part + "}")
                    i = end
        else:
            out.append("\\" + esc)
        i += 1

    return "".join(out)


def _decode_multiline(content: str) -> str:
    # Minimal normalization for PoC: CRLF/CR -> LF.
    return content.replace("\r\n", "\n").replace("\r", "\n")


def _is_ident_continue(ch: str) -> bool:
    if not ch:
        return False
    if ch in _DISALLOWED_IDENT_CHARS:
        return False
    if ch in _UNICODE_SPACES or ch in _NEWLINES:
        return False
    return True


__all__ = [
    "CSTArgEntry",
    "CSTDocument",
    "CSTEntry",
    "CSTIdentifier",
    "CSTNode",
    "CSTPropEntry",
    "CSTTypeAnnotation",
    "CSTValue",
    "KDL2CSTParser",
    "KDLParseError",
    "KDLLexer",
    "Position",
    "Span",
    "Token",
    "TokenType",
]
