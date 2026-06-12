import os


def _escape_md_cell(value):
    if value is None:
        return ""
    text = str(value)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("|", r"\|")
    text = text.replace("\n", "<br>")
    return text.strip()


def _sheet_to_markdown(sheet):
    rows = list(sheet.iter_rows(values_only=True))
    if not rows:
        return "_(empty sheet)_\n\n"

    last_row_idx = -1
    last_col_idx = -1
    for r_idx, row in enumerate(rows):
        for c_idx, value in enumerate(row):
            if value is not None and str(value).strip() != "":
                last_row_idx = max(last_row_idx, r_idx)
                last_col_idx = max(last_col_idx, c_idx)

    if last_row_idx < 0 or last_col_idx < 0:
        return "_(empty sheet)_\n\n"

    trimmed = [row[: last_col_idx + 1] for row in rows[: last_row_idx + 1]]
    normalized_rows = [[_escape_md_cell(cell) for cell in row] for row in trimmed]

    header = normalized_rows[0]
    if all(cell == "" for cell in header):
        header = [f"Column {i+1}" for i in range(len(header))]

    lines = []
    lines.append("| " + " | ".join(header) + " |")
    lines.append("| " + " | ".join(["---"] * len(header)) + " |")

    for row in normalized_rows[1:]:
        if len(row) < len(header):
            row += [""] * (len(header) - len(row))
        lines.append("| " + " | ".join(row) + " |")

    return "\n".join(lines) + "\n\n"


def convert_xlsx_to_md(file_path):
    """
    Converts a .xlsx file to Markdown.
    Each sheet is emitted as a section with a markdown table.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    try:
        from openpyxl import load_workbook
    except ImportError as e:
        raise ImportError("openpyxl is required for .xlsx conversion") from e

    workbook = load_workbook(file_path, data_only=True)
    output = []

    for sheet in workbook.worksheets:
        output.append(f"## {sheet.title}\n\n")
        output.append(_sheet_to_markdown(sheet))

    return "".join(output).strip() + "\n"

