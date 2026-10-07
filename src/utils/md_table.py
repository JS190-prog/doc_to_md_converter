"""Shared Markdown table helpers (used by the xls/xlsx/docx converters)."""

from __future__ import annotations

import datetime as _dt


def format_cell(value) -> str:
    """Render a spreadsheet/table cell value as clean text."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, float) and value.is_integer():
        # xlrd returns every number as float: 1.0 -> 1
        return str(int(value))
    if isinstance(value, _dt.datetime):
        if value.time() == _dt.time(0):
            return value.date().isoformat()
        return value.isoformat(sep=" ")
    return str(value)


def escape_md_cell(value) -> str:
    text = format_cell(value)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("|", r"\|")
    text = text.replace("\n", "<br>")
    return text.strip()


def rows_to_markdown(rows) -> str:
    """Convert a list of row sequences into a Markdown table.

    The first row is used as the header. Trailing empty rows/columns are
    trimmed. Returns an italic placeholder for an entirely empty grid.
    """
    last_row = -1
    last_col = -1
    for r_idx, row in enumerate(rows):
        for c_idx, value in enumerate(row):
            if value is not None and str(value).strip() != "":
                last_row = max(last_row, r_idx)
                last_col = max(last_col, c_idx)

    if last_row < 0 or last_col < 0:
        return "_(empty sheet)_\n\n"

    width = last_col + 1
    grid = []
    for row in rows[: last_row + 1]:
        cells = [escape_md_cell(cell) for cell in list(row)[:width]]
        cells += [""] * (width - len(cells))
        grid.append(cells)

    header = grid[0]
    if all(cell == "" for cell in header):
        header = [f"Column {i + 1}" for i in range(width)]

    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(["---"] * width) + " |",
    ]
    for row in grid[1:]:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines) + "\n\n"
