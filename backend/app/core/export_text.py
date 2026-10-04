"""Sanitizers for the text sinks exports write user content into.

Exports carry Reddit text, code names and memo bodies verbatim, and each
destination format misreads a different set of characters:

* spreadsheets (CSV, XLSX) evaluate a cell that looks like a formula --
  ``=HYPERLINK(...)`` in a quote must arrive as text, not run;
* XML-based formats (QDC, DOCX, XLSX) forbid most C0 control characters
  outright -- ElementTree writes them through and produces a file nothing
  can open, while openpyxl and python-docx raise mid-export;
* markdown treats a newline, a leading ``#`` or raw HTML in an
  interpolated heading or table cell as structure.

Each sink calls the one function here that matches it, so the rules live
in one place rather than drifting between writers.
"""

from __future__ import annotations

import re
from typing import Any

# XML 1.0 Char production: everything below U+0020 except tab/LF/CR, the
# surrogate block (a lone surrogate can't be encoded as UTF-8 at all), and
# the two noncharacters U+FFFE/U+FFFF.
_XML_ILLEGAL_RE = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff￾￿]")

# A cell a spreadsheet would evaluate. Excel and LibreOffice skip leading
# whitespace before deciding, so " =1+1" and "\n=1+1" count too.
_FORMULA_TRIGGERS = ("=", "+", "-", "@")
_FORMULA_LEADING_CONTROL = ("\t", "\r", "\n")


def xml_safe(value: Any) -> str:
    """``value`` as text with every character XML 1.0 forbids removed."""
    if value is None:
        return ""
    return _XML_ILLEGAL_RE.sub("", str(value))


def neutralize_formula(value: str) -> str:
    """Prefix ``'`` to a string a spreadsheet would read as a formula.

    Only strings: a numeric cell (a negative score) is the caller's to
    pass through untouched.
    """
    if value.startswith(_FORMULA_LEADING_CONTROL) or value.lstrip().startswith(_FORMULA_TRIGGERS):
        return "'" + value
    return value


# Only a marker followed by whitespace (or nothing) opens a block, so
# "-3" and "3.5" are left alone.
_MD_LEADING_BLOCK_RE = re.compile(r"^(\s*)(?:([#+\-*])|(\d+)([.)]))(?=\s|$)")


def _escape_block_marker(match: re.Match[str]) -> str:
    indent, marker, digits, punct = match.groups()
    if marker is not None:
        return f"{indent}\\{marker}"
    return f"{indent}{digits}\\{punct}"


def md_inline(value: Any) -> str:
    """One line of markdown text for a heading or table cell.

    Newlines are flattened (a newline in a filename must not start a new
    block), pipes escaped (they would split a table row), raw HTML
    neutralized (a viewer that renders HTML must not run a ``<script>``
    carried in a code name), and a leading block marker escaped so a
    value like ``# not a heading`` stays text. Free-form bodies -- a memo,
    a stored summary -- are the user's own markdown and are not passed
    through this.
    """
    if value is None:
        return ""
    text = str(value).replace("\r\n", " ").replace("\n", " ").replace("\r", " ").strip()
    # CommonMark backslash escapes: a `\<` can't open an HTML tag, and
    # unlike `&lt;` it still reads as `<` in a plain-text viewer.
    text = text.replace("\\", "\\\\").replace("<", "\\<").replace(">", "\\>").replace("|", "\\|")
    return _MD_LEADING_BLOCK_RE.sub(_escape_block_marker, text, count=1)
