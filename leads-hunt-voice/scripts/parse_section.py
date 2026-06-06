"""Pure-stdlib markdown section parser for style.md editing.

A "section" is the body between a heading line (e.g. `## Foo`) and the next
heading of equal or higher level (i.e. with the same number of `#` or fewer).

Heading match is exact on the trimmed text after the `#` prefix, so
`## Rhythm & cadence (used by drafting)` matches that exact title.

Used by voice.py. No external deps.
"""
from __future__ import annotations

import re
from typing import Optional


_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


def _heading_level(line: str) -> Optional[int]:
    """Return the heading level (1-6) of a line, or None if not a heading."""
    m = _HEADING_RE.match(line)
    if not m:
        return None
    return len(m.group(1))


def _heading_text(line: str) -> Optional[str]:
    m = _HEADING_RE.match(line)
    if not m:
        return None
    return m.group(2).strip()


def find_heading(text: str, heading: str) -> Optional[int]:
    """Return the byte offset where the heading line starts, or None.

    `heading` is the full heading including `#` markers, e.g. `## Rhythm & cadence (used by drafting)`.
    """
    target_level = _heading_level(heading)
    target_text = _heading_text(heading)
    if target_level is None or target_text is None:
        return None
    offset = 0
    for line in text.splitlines(keepends=True):
        if _heading_level(line.rstrip("\n")) == target_level and \
                _heading_text(line.rstrip("\n")) == target_text:
            return offset
        offset += len(line)
    return None


def _section_bounds(text: str, heading: str) -> Optional[tuple[int, int, int]]:
    """Return (heading_start, body_start, body_end) byte offsets, or None.

    body_start is the offset just after the heading line's newline.
    body_end is the offset of the next equal-or-higher heading (or end of file).
    """
    target_level = _heading_level(heading)
    target_text = _heading_text(heading)
    if target_level is None or target_text is None:
        return None

    lines = text.splitlines(keepends=True)
    offsets = []
    cur = 0
    for ln in lines:
        offsets.append(cur)
        cur += len(ln)
    offsets.append(cur)  # sentinel: total length

    heading_idx = None
    for i, ln in enumerate(lines):
        stripped = ln.rstrip("\n")
        if _heading_level(stripped) == target_level and _heading_text(stripped) == target_text:
            heading_idx = i
            break
    if heading_idx is None:
        return None

    body_start = offsets[heading_idx + 1]
    body_end = offsets[-1]
    for j in range(heading_idx + 1, len(lines)):
        stripped = lines[j].rstrip("\n")
        lvl = _heading_level(stripped)
        if lvl is not None and lvl <= target_level:
            body_end = offsets[j]
            break
    return offsets[heading_idx], body_start, body_end


def read_section(text: str, heading: str) -> Optional[str]:
    """Return the body of `heading` (everything until the next equal/higher heading).

    Returns None if the heading is not found. Returned body includes its trailing
    newlines as in the source, but is stripped of the heading line itself.
    """
    bounds = _section_bounds(text, heading)
    if bounds is None:
        return None
    _, body_start, body_end = bounds
    return text[body_start:body_end]


def replace_section(text: str, heading: str, new_body: str) -> str:
    """Replace the body of `heading` with `new_body`. Heading line is preserved.

    `new_body` should end with a newline (caller's responsibility) so the next
    heading starts on a fresh line. If it doesn't, one is added.
    """
    bounds = _section_bounds(text, heading)
    if bounds is None:
        raise KeyError(f"heading not found: {heading!r}")
    _, body_start, body_end = bounds
    if new_body and not new_body.endswith("\n"):
        new_body = new_body + "\n"
    return text[:body_start] + new_body + text[body_end:]


def append_under_heading(text: str, heading: str, new_line: str) -> str:
    """Append `new_line` to the end of the section under `heading`.

    Trailing blank lines in the existing body are preserved after the appended
    line so the section still has visual breathing room before the next heading.
    `new_line` is appended verbatim, with a trailing newline if missing.
    """
    body = read_section(text, heading)
    if body is None:
        raise KeyError(f"heading not found: {heading!r}")
    if not new_line.endswith("\n"):
        new_line = new_line + "\n"

    # Split body into "content" and "trailing blank lines" so we insert before the
    # blanks (keeps the gap before the next ## heading).
    lines = body.splitlines(keepends=True)
    tail_blank = 0
    for ln in reversed(lines):
        if ln.strip() == "":
            tail_blank += 1
        else:
            break
    head = "".join(lines[: len(lines) - tail_blank]) if tail_blank else body
    tail = "".join(lines[len(lines) - tail_blank:]) if tail_blank else ""

    if head and not head.endswith("\n"):
        head = head + "\n"
    new_body = head + new_line + tail
    return replace_section(text, heading, new_body)
