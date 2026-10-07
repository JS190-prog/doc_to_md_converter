import os

from src.utils.md_table import rows_to_markdown

# xlrd cell types
_XL_CELL_DATE = 3
_XL_CELL_BOOLEAN = 4
_XL_CELL_ERROR = 5


def _sheet_rows(sheet, datemode, xlrd):
    """Yield rows with dates/booleans/errors decoded (xlrd returns raw floats)."""
    for r_idx in range(sheet.nrows):
        row = []
        for cell in sheet.row(r_idx):
            if cell.ctype == _XL_CELL_DATE:
                try:
                    row.append(xlrd.xldate.xldate_as_datetime(cell.value, datemode))
                except Exception:
                    row.append(cell.value)
            elif cell.ctype == _XL_CELL_BOOLEAN:
                row.append(bool(cell.value))
            elif cell.ctype == _XL_CELL_ERROR:
                row.append("#ERR")
            else:
                row.append(cell.value)
        yield row


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
            rows = list(_sheet_rows(sheet, workbook.datemode, xlrd))
            output.append(rows_to_markdown(rows) if rows else "_(empty sheet)_\n\n")
    finally:
        workbook.release_resources()

    return "".join(output).strip() + "\n"
