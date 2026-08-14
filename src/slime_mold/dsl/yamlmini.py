"""A compact YAML subset parser (no external dependencies).

SlimeMold's engine intentionally has no runtime dependencies so that it can be
embedded in CI, notebooks or Pyodide web workers. The DSL is a simple subset of
YAML (indentation-block mappings, dash sequences, inline scalars, inline lists
and inline dicts). If the full ``PyYAML`` package happens to be installed it is
used instead; otherwise this parser covers everything the SlimeMold DSL needs.

Supported syntax::

    top:
      key: value            # comment
      list:
        - a
        - id: b             # dict-in-list
          other: 2          # continuation of the same dict
      inline: [1, 2, 3]
      nested:
        x: {a: 1, b: 2}
"""

from __future__ import annotations

import re
from typing import Any


def parse_yaml(text: str) -> Any:
    """Parse a YAML-subset document into Python objects."""
    try:
        import yaml  # type: ignore

        return yaml.safe_load(text)
    except ImportError:
        pass
    lines = _strip_comments(text)
    if not lines:
        return None
    obj, _ = _parse_block(lines, 0, indent_of(lines))
    return obj


def _strip_comments(text: str) -> list[str]:
    out: list[str] = []
    for raw in text.splitlines():
        if not raw.strip():
            continue
        if raw.lstrip().startswith("#"):
            continue
        out.append(_strip_trailing_comment(raw).rstrip())
    return out


def _strip_trailing_comment(line: str) -> str:
    in_single = False
    in_double = False
    for i, ch in enumerate(line):
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "#" and not in_single and not in_double and (i == 0 or line[i - 1] in " \t"):
            return line[:i]
    return line


def indent_of(lines: list[str]) -> int:
    for line in lines:
        if line.strip():
            return len(line) - len(line.lstrip())
    return 0


def _parse_block(lines: list[str], start: int, indent: int) -> tuple[Any, int]:
    """Parse a block of lines at a given indentation.

    Returns ``(obj, next_idx)`` where ``obj`` is a dict (all map entries) or a
    list (all dash items).
    """
    entries: list[dict] = []  # {"key": ..., "value": ...} map entries
    seq_items: list[Any] = []
    is_seq = False
    is_map = False
    i = start
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        cur_indent = len(line) - len(line.lstrip())
        if cur_indent < indent:
            break
        if cur_indent > indent:
            raise ValueError(f"unexpected indentation at line {i + 1}: {line!r}")
        content = line.strip()
        if content == "-" or content.startswith("- "):
            is_seq = True
            item, i = _parse_seq_item(lines, i, indent)
            seq_items.append(item)
            continue
        if ":" not in content:
            raise ValueError(f"expected 'key: value' at line {i + 1}: {line!r}")
        is_map = True
        key, _, rest = content.partition(":")
        key = _scalar(key.strip())
        rest = rest.strip()
        if rest:
            entries.append({"key": key, "value": _parse_inline(rest)})
            i += 1
            continue
        # value is a nested block
        nxt_idx = i + 1
        if nxt_idx < len(lines) and lines[nxt_idx].strip():
            nxt_indent = len(lines[nxt_idx]) - len(lines[nxt_idx].lstrip())
            if nxt_indent > indent:
                child, ni = _parse_block(lines, nxt_idx, nxt_indent)
                entries.append({"key": key, "value": child})
                i = ni
                continue
        entries.append({"key": key, "value": None})
        i += 1

    if is_seq and is_map:
        raise ValueError(f"cannot mix mapping and sequence entries in one block (line {start + 1})")
    if is_seq:
        return seq_items, i
    result: dict[str, Any] = {}
    for entry in entries:
        result[entry["key"]] = entry["value"]
    return result, i


def _parse_seq_item(lines: list[str], idx: int, indent: int) -> tuple[Any, int]:
    """Parse one ``- item`` including its indented continuation lines."""
    line = lines[idx]
    dash_indent = len(line) - len(line.lstrip())
    content = line.strip()[2:].strip()

    if not content:
        item: Any = {}
    elif content[0] in "[{":
        # inline list/dict as a sequence item; cannot have child lines
        return _parse_inline(content), idx + 1
    elif ":" in content:
        key, _, rest = content.partition(":")
        key = _scalar(key.strip())
        rest = rest.strip()
        item = {key: _parse_inline(rest) if rest else None}
    else:
        item = _parse_inline(content)
        # scalar items cannot have children
        return item, idx + 1

    i = idx + 1
    while i < len(lines):
        nxt = lines[i]
        if not nxt.strip():
            i += 1
            continue
        nxt_indent = len(nxt) - len(nxt.lstrip())
        if nxt_indent <= dash_indent:
            break
        ncontent = nxt.strip()
        if ":" not in ncontent:
            raise ValueError(f"expected 'key: value' in sequence item, line {i + 1}")
        key, _, rest = ncontent.partition(":")
        key = _scalar(key.strip())
        rest = rest.strip()
        if rest:
            item[key] = _parse_inline(rest)
            i += 1
            continue
        if i + 1 < len(lines) and lines[i + 1].strip():
            n2 = lines[i + 1]
            n2_indent = len(n2) - len(n2.lstrip())
            if n2_indent > nxt_indent:
                child, ni = _parse_block(lines, i + 1, n2_indent)
                item[key] = child
                i = ni
                continue
        item[key] = None
        i += 1
    return item, i


def _scalar(raw: str) -> Any:
    raw = raw.strip()
    if raw.startswith('"') and raw.endswith('"') and len(raw) >= 2:
        return raw[1:-1]
    if raw.startswith("'") and raw.endswith("'") and len(raw) >= 2:
        return raw[1:-1]
    low = raw.lower()
    if low in ("null", "~"):
        return None
    if low in ("true", "yes", "on"):
        return True
    if low in ("false", "no", "off"):
        return False
    if re.fullmatch(r"[-+]?\d+", raw):
        return int(raw)
    if re.fullmatch(r"[-+]?(\d+\.\d*|\.\d+|\d+)([eE][-+]?\d+)?", raw):
        return float(raw)
    return raw


def _parse_inline(raw: str) -> Any:
    raw = raw.strip()
    if raw == "":
        return None
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1]
        if not inner.strip():
            return []
        return [_parse_inline(x) for x in _split_top(inner)]
    if raw.startswith("{") and raw.endswith("}"):
        inner = raw[1:-1]
        d: dict[str, Any] = {}
        for part in _split_top(inner):
            k, _, v = part.partition(":")
            d[_scalar(k.strip())] = _parse_inline(v.strip())
        return d
    return _scalar(raw)


def _split_top(inner: str) -> list[str]:
    parts: list[str] = []
    depth = 0
    cur: list[str] = []
    in_s = False
    in_d = False
    for ch in inner:
        if ch == "'" and not in_d:
            in_s = not in_s
        elif ch == '"' and not in_s:
            in_d = not in_d
        if ch in "[{" and not in_s and not in_d:
            depth += 1
        elif ch in "]}" and not in_s and not in_d:
            depth -= 1
        if ch == "," and depth == 0 and not in_s and not in_d:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    if cur:
        parts.append("".join(cur))
    return parts
