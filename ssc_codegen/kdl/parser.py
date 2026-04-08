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
    has_children_block: bool = False
    children_block_span: Span | None = None


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

# Bare identifiers that are reserved in KDL2 (must use # prefix or quotes)
_RESERVED_BARE_IDS = {"true", "false", "null", "inf", "nan", "-inf"}


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
            # KDL2: multiline string content must begin with a newline
            if not self.c.eof() and not (self.c.startswith("\r\n") or self.c.cur() in _NEWLINES):
                raise KDLParseError(
                    "Multiline string must begin with a newline immediately after opening \"\"\"",
                    line=start.line, column=start.column, offset=start.offset,
                )
            content_start = self.c.i
            while not self.c.eof():
                if self.c.startswith('"""'):
                    content = self.c.src[content_start : self.c.i]
                    self.c.advance(3)
                    raw = self.c.src[start.offset : self.c.i]
                    try:
                        value = _decode_multiline(content, is_raw=False)
                    except ValueError as exc:
                        raise KDLParseError(
                            str(exc), line=start.line, column=start.column, offset=start.offset
                        ) from exc
                    return Token(TokenType.STRING, raw, value, Span(start, self.c.pos()))
                if self.c.startswith("\\"):
                    if self._try_consume_escline():
                        continue
                    # Non-escline escape (e.g. \"): consume \ and the escaped char
                    # so the next char is not mistaken for the closing """
                    self.c.advance()
                    if not self.c.eof():
                        self.c.advance()
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
        while not self.c.eof():
            ch = self.c.cur()
            if ch == "\\":
                self.c.advance()  # consume backslash
                if self.c.eof():
                    break
                # whitespace escape: consume \ and all following whitespace (including newlines)
                if self.c.cur() in _UNICODE_SPACES or self.c.cur() in _NEWLINES or self.c.startswith("\r\n"):
                    while not self.c.eof():
                        if self.c.startswith("\r\n"):
                            self.c.advance(2)
                        elif self.c.cur() in _NEWLINES or self.c.cur() in _UNICODE_SPACES:
                            self.c.advance()
                        else:
                            break
                else:
                    self.c.advance()  # consume the single escaped char
                continue
            if self.c.startswith("\r\n"):
                pos = self.c.pos()
                raise KDLParseError(
                    "Newline in quoted string",
                    line=pos.line,
                    column=pos.column,
                    offset=pos.offset,
                )
            if ch in _NEWLINES:
                pos = self.c.pos()
                raise KDLParseError(
                    "Newline in quoted string",
                    line=pos.line,
                    column=pos.column,
                    offset=pos.offset,
                )
            if ch == '"':
                self.c.advance()
                raw = self.c.src[start.offset : self.c.i]
                try:
                    value = _decode_quoted(raw)
                except ValueError as exc:
                    raise KDLParseError(
                        str(exc), line=start.line, column=start.column, offset=start.offset,
                    ) from exc
                return Token(TokenType.STRING, raw, value, Span(start, self.c.pos()))
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
        # KDL2: multiline raw string content must begin with a newline
        if qlen == 3:
            if not self.c.eof() and not (self.c.startswith("\r\n") or self.c.cur() in _NEWLINES):
                raise KDLParseError(
                    "Multiline raw string must begin with a newline immediately after opening delimiter",
                    line=start.line, column=start.column, offset=start.offset,
                )
        content_start = self.c.i

        while not self.c.eof():
            if self.c.startswith(closing):
                content = self.c.src[content_start : self.c.i]
                self.c.advance(len(closing))
                raw = self.c.src[start.offset : self.c.i]
                if qlen == 3:
                    try:
                        value = _decode_multiline(content, is_raw=True)
                    except ValueError as exc:
                        raise KDLParseError(
                            str(exc), line=start.line, column=start.column, offset=start.offset
                        ) from exc
                else:
                    value = content
                return Token(TokenType.STRING, raw, value, Span(start, self.c.pos()))

            # single-quote raw strings cannot contain newlines
            if qlen == 1 and (self.c.startswith("\r\n") or self.c.cur() in _NEWLINES):
                raise KDLParseError(
                    "Newline in single-quote raw string",
                    line=start.line, column=start.column, offset=start.offset,
                )
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
                if _is_ident_continue(self.c.cur()):
                    raise KDLParseError(
                        f"Invalid number: {raw!r} immediately followed by {self.c.cur()!r}",
                        line=start.line, column=start.column, offset=start.offset,
                    )
                return Token(typ, raw, value, Span(start, self.c.pos()))

        m = _DECIMAL_RE.match(rem)
        if m:
            raw = m.group(0)
            start = self.c.pos()
            self.c.advance(len(raw))
            if _is_ident_continue(self.c.cur()):
                raise KDLParseError(
                    f"Invalid number: {raw!r} immediately followed by {self.c.cur()!r}",
                    line=start.line, column=start.column, offset=start.offset,
                )
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
            self._check_disallowed_literal()
            self.c.advance()

        raw = self.c.src[start.offset : self.c.i]
        if raw in _RESERVED_BARE_IDS:
            raise KDLParseError(
                f"Reserved identifier {raw!r} is not valid as a bare identifier in KDL2",
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
                consumed = self._consume_terminators()
                if not consumed and not self._at(TokenType.EOF):
                    raise self._error_here("Expected newline or semicolon after node")
                self._skip_separators()
                continue

            nodes.append(self._parse_node())
            consumed = self._consume_terminators()
            if not consumed and not self._at(TokenType.EOF):
                raise self._error_here("Expected newline or semicolon after node")
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
        has_children_block = False
        children_block_span: Span | None = None

        # Zero-space: track end offset of last significant token before each entry
        prev_end = name.span.end.offset

        while not self._is_node_terminator() and not self._at(TokenType.LBRACE):
            if self._match(TokenType.SLASHDASH):
                self._skip_separators()
                if self._at(TokenType.LBRACE):
                    # Slashdash-discarded children block: after this, no more entries
                    # are allowed (children-block position reached). Discard it and
                    # exit the entries loop so the "while True" block takes over.
                    self._discard_children_block()
                    break
                self._parse_discarded_component(allow_node=False)
                # Do NOT skip separators here: leave newlines to terminate the node
                continue
            # Require whitespace before each entry
            next_tok = self._peek()
            if next_tok.span.start.offset == prev_end:
                raise self._error_tok(next_tok, "Expected whitespace before entry")
            entry = self._parse_entry()
            prev_end = entry.span.end.offset
            entries.append(entry)

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
            if has_children_block:
                raise self._error_here("Node cannot have multiple children blocks")
            has_children_block = True
            lbrace = self._prev()

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
            rbrace = self._expect(TokenType.RBRACE)
            children_block_span = Span(lbrace.span.start, rbrace.span.end)
            # Do NOT call _skip_separators() here: leave any trailing newlines
            # for the document/parent level to consume as node terminators.

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
            has_children_block=has_children_block,
            children_block_span=children_block_span,
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

    def _consume_terminators(self) -> bool:
        consumed = False
        while self._match(TokenType.NEWLINE) or self._match(TokenType.SEMI):
            consumed = True
        return consumed

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
    """Decode a quoted string. Raises ValueError for invalid escape sequences."""
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
            raise ValueError("Unterminated escape sequence at end of string")

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
        elif esc == '"':
            out.append('"')
        elif esc == "u" and i + 1 < len(body) and body[i + 1] == "{":
            end = body.find("}", i + 2)
            if end == -1:
                raise ValueError("Unterminated \\u{} escape sequence")
            hex_part = body[i + 2 : end]
            if not (1 <= len(hex_part) <= 6) or not all(c in "0123456789abcdefABCDEF" for c in hex_part):
                raise ValueError(f"Invalid \\u{{}} escape: \\u{{{hex_part}}}")
            cp = int(hex_part, 16)
            if 0xD800 <= cp <= 0xDFFF:
                raise ValueError(f"Surrogate code point U+{cp:04X} is not a valid Unicode scalar value")
            if cp > 0x10FFFF:
                raise ValueError(f"Code point U+{cp:X} exceeds maximum Unicode scalar value U+10FFFF")
            out.append(chr(cp))
            i = end
        elif esc == "s":
            out.append(" ")
        elif esc in _UNICODE_SPACES or esc in _NEWLINES:
            # whitespace escape: skip \ and all consecutive whitespace
            while i < len(body) and (body[i] in _UNICODE_SPACES or body[i] in _NEWLINES):
                i += 1
            continue
        else:
            raise ValueError(f"Invalid escape sequence: \\{esc}")
        i += 1

    return "".join(out)


def _count_trailing_backslashes(s: str) -> int:
    count = 0
    i = len(s) - 1
    while i >= 0 and s[i] == "\\":
        count += 1
        i -= 1
    return count


def _extract_prefix_from_closing_raw(raw: str) -> str:
    """Determine the indent prefix from the closing-delimiter line raw string.

    The prefix is all initial literal Unicode-whitespace characters.  Any
    whitespace-escape sequence (``\\<ws>`` or ``\\s``) that follows terminates
    the literal prefix region and is itself silently consumed.  Anything else
    on the closing line is an error.
    """
    i = 0
    prefix_chars: list[str] = []
    while i < len(raw):
        ch = raw[i]
        if ch in _UNICODE_SPACES:
            prefix_chars.append(ch)
            i += 1
        elif ch == "\\":
            i += 1
            if i >= len(raw):
                raise ValueError("Unterminated escape on closing delimiter line")
            esc = raw[i]
            if esc in _UNICODE_SPACES or esc in _NEWLINES:
                # Whitespace escape: consume all following whitespace; no prefix contribution.
                while i < len(raw) and (raw[i] in _UNICODE_SPACES or raw[i] in _NEWLINES):
                    i += 1
            elif esc == "s":
                # \\s = single space: also terminates the literal prefix region.
                i += 1
            else:
                raise ValueError(
                    f"Non-whitespace escape on closing delimiter line: \\{esc!r}"
                )
        else:
            raise ValueError(
                f"Non-whitespace character on closing delimiter line: {ch!r}"
            )
    return "".join(prefix_chars)


def _multiline_extract_prefix(
    lines: list[str], *, is_raw: bool
) -> tuple[str, list[str]]:
    """Return (prefix, content_lines) from the split lines of a multiline string body.

    The closing-delimiter's indentation defines the required prefix.
    Two cases:
    - Normal: the last element of *lines* is the closing-delimiter's line.
    - Escline-before-close: the second-to-last line ends with an odd number of
      backslashes (an escline), meaning its trailing ``\\`` + the following newline
      was consumed by the escline mechanism.  The "effective closing raw" is the
      content before that ``\\`` concatenated with the last line.  If that combined
      text is not purely whitespace, a ValueError is raised.
    """
    if not is_raw and len(lines) >= 2:
        n = _count_trailing_backslashes(lines[-2])
        if n % 2 == 1:
            # Escline connects the second-to-last line into the closing delimiter.
            effective_closing = lines[-2][:-1] + lines[-1]
            prefix = _extract_prefix_from_closing_raw(effective_closing)
            return prefix, lines[:-2]

    closing_raw = lines[-1]
    prefix = _extract_prefix_from_closing_raw(closing_raw)
    return prefix, lines[:-1]


def _multiline_resolve_esclines(lines: list[str]) -> list[str]:
    """Merge continuation lines created by esclines (lines ending with odd-count backslashes)."""
    result: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        n = _count_trailing_backslashes(line)
        if n % 2 == 1:
            # Escline: strip the single trailing backslash and merge with next line.
            merged = line[:-1]
            i += 1
            while i < len(lines):
                nxt = lines[i]
                n2 = _count_trailing_backslashes(nxt)
                if n2 % 2 == 1:
                    merged += nxt[:-1]
                    i += 1
                else:
                    merged += nxt
                    i += 1
                    break
            result.append(merged)
        else:
            result.append(line)
            i += 1
    return result


def _decode_multiline(content: str, *, is_raw: bool = False) -> str:
    text = content.replace("\r\n", "\n").replace("\r", "\n")
    if text.startswith("\n"):
        text = text[1:]

    lines = text.split("\n")

    # Determine prefix and separate content lines from the closing-delimiter section.
    prefix, content_lines = _multiline_extract_prefix(lines, is_raw=is_raw)

    # For non-raw strings, merge continuation lines produced by esclines.
    if not is_raw:
        logical_lines = _multiline_resolve_esclines(content_lines)
    else:
        logical_lines = content_lines

    # Every non-blank logical line must literally start with the prefix.
    # Blank lines (lines consisting entirely of Unicode whitespace) are exempt from
    # prefix validation and are treated as empty lines.
    result_lines: list[str] = []
    for line in logical_lines:
        if not line or all(c in _UNICODE_SPACES for c in line):
            result_lines.append("")
        elif line.startswith(prefix):
            result_lines.append(line[len(prefix):])
        else:
            raise ValueError(
                f"Content line does not match required prefix {prefix!r}: {line!r}"
            )
    result = "\n".join(result_lines)

    if not is_raw:
        result = _decode_escape_body(result)

    return result


def _decode_escape_body(body: str) -> str:
    """Decode KDL2 escape sequences in an already-stripped string body."""
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
            raise ValueError("Unterminated escape sequence at end of string")
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
        elif esc == '"':
            out.append('"')
        elif esc == "u" and i + 1 < len(body) and body[i + 1] == "{":
            end = body.find("}", i + 2)
            if end == -1:
                raise ValueError("Unterminated \\u{} escape sequence")
            hex_part = body[i + 2 : end]
            if not (1 <= len(hex_part) <= 6) or not all(
                c in "0123456789abcdefABCDEF" for c in hex_part
            ):
                raise ValueError(f"Invalid \\u{{}} escape: \\u{{{hex_part}}}")
            cp = int(hex_part, 16)
            if 0xD800 <= cp <= 0xDFFF:
                raise ValueError(
                    f"Surrogate code point U+{cp:04X} is not a valid Unicode scalar value"
                )
            if cp > 0x10FFFF:
                raise ValueError(
                    f"Code point U+{cp:X} exceeds maximum Unicode scalar value U+10FFFF"
                )
            out.append(chr(cp))
            i = end
        elif esc == "s":
            out.append(" ")
        elif esc in _UNICODE_SPACES or esc in _NEWLINES:
            # Whitespace escape: consume \ and all following whitespace/newlines.
            while i < len(body) and (body[i] in _UNICODE_SPACES or body[i] in _NEWLINES):
                i += 1
            continue
        else:
            raise ValueError(f"Invalid escape sequence: \\{esc}")
        i += 1
    return "".join(out)


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
