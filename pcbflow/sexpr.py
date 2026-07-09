"""Minimal S-expression parser/serializer for KiCad file formats.

S-expressions are represented as nested Python lists. Atoms are:
  - ``Sym`` (unquoted token, e.g. ``kicad_sch`` or ``1.27``)
  - ``QStr`` (double-quoted string)
Numbers written by the serializer are formatted the way KiCad expects
(trailing zeros stripped, at most 4 decimals).
"""

from __future__ import annotations


class Sym(str):
    """Unquoted atom."""

    __slots__ = ()


class QStr(str):
    """Double-quoted string atom."""

    __slots__ = ()


def parse(text: str):
    """Parse a document containing a single top-level s-expression."""
    tokens = _tokenize(text)
    pos = 0

    def read():
        nonlocal pos
        tok = tokens[pos]
        pos += 1
        if tok == "(":
            out = []
            while tokens[pos] != ")":
                out.append(read())
            pos += 1
            return out
        if isinstance(tok, (Sym, QStr)):
            return tok
        raise ValueError(f"unexpected token {tok!r}")

    expr = read()
    if pos != len(tokens):
        raise ValueError("trailing tokens after top-level expression")
    return expr


def _tokenize(text: str):
    tokens = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c in " \t\r\n":
            i += 1
        elif c in "()":
            tokens.append(c)
            i += 1
        elif c == '"':
            j = i + 1
            buf = []
            while j < n:
                ch = text[j]
                if ch == "\\" and j + 1 < n:
                    buf.append(ch)
                    buf.append(text[j + 1])
                    j += 2
                    continue
                if ch == '"':
                    break
                buf.append(ch)
                j += 1
            tokens.append(QStr("".join(buf)))
            i = j + 1
        else:
            j = i
            while j < n and text[j] not in ' \t\r\n()"':
                j += 1
            tokens.append(Sym(text[i:j]))
            i = j
    return tokens


def fmt_num(v) -> str:
    if isinstance(v, bool):
        raise TypeError("bool is not a KiCad number")
    if isinstance(v, int):
        return str(v)
    s = f"{v:.4f}".rstrip("0").rstrip(".")
    return s if s not in ("-0", "") else "0"


def dump(expr, indent: int = 0) -> str:
    """Serialize with KiCad-style indentation."""
    pad = "\t" * indent
    if isinstance(expr, QStr):
        return '"' + expr + '"'
    if isinstance(expr, Sym):
        return str(expr)
    if isinstance(expr, (int, float)):
        return fmt_num(expr)
    if not isinstance(expr, list):
        raise TypeError(f"cannot serialize {type(expr)}")

    parts = [dump(e) if not isinstance(e, list) else None for e in expr]
    if all(p is not None for p in parts):
        return "(" + " ".join(parts) + ")"

    # Mixed atoms and sublists: atoms on the head line, sublists indented.
    head = []
    k = 0
    while k < len(expr) and not isinstance(expr[k], list):
        head.append(dump(expr[k]))
        k += 1
    lines = ["(" + " ".join(head)]
    for e in expr[k:]:
        lines.append(pad + "\t" + dump(e, indent + 1))
    lines.append(pad + ")")
    return "\n".join(lines)


def find(expr, tag: str):
    """First child list whose head is *tag*."""
    for e in expr:
        if isinstance(e, list) and e and e[0] == tag:
            return e
    return None


def find_all(expr, tag: str):
    return [e for e in expr if isinstance(e, list) and e and e[0] == tag]
