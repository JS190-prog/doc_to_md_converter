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
    rows = [sheet.row_values(i) for i in range(sheet.nrows)]
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


def convert_xls_to_md(file_path):
    """
    Converts a .xls file to Markdown.
    Each sheet is emitted as a section with a markdown table.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    try:
        import xlrd
    except ImportError as e:
        raise ImportError("xlrd is required for .xls conversion") from e

    workbook = xlrd.open_workbook(file_path, on_demand=True)
    output = []

    try:
        for sheet_name in workbook.sheet_names():
            sheet = workbook.sheet_by_name(sheet_name)
            output.append(f"## {sheet_name}\n\n")
            output.append(_sheet_to_markdown(sheet))
    finally:
        workbook.release_resources()

    return "".join(output).strip() + "\n"

