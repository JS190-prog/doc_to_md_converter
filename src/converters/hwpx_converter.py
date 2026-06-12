import re
import zipfile
from xml.etree import ElementTree as ET


class HWPXConversionError(Exception):
    pass


def _local_name(tag):
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def _section_sort_key(path):
    m = re.search(r"section(\d+)\.xml$", path.lower())
    if m:
        return int(m.group(1))
    return 10**9


def _extract_text_from_section_xml(xml_bytes):
    root = ET.fromstring(xml_bytes)

    lines = []
    current = []

    def flush_line():
        text = "".join(current).strip()
        if text:
            lines.append(text)
        current.clear()

    for elem in root.iter():
        name = _local_name(elem.tag).lower()
        if name in ("p",):
            flush_line()
            continue
        if name in ("t", "text") and elem.text:
            current.append(elem.text)
        elif name in ("linebreak", "br"):
            current.append("\n")

    flush_line()
    text = "\n\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text


def convert_hwpx_to_md(file_path):
    if not zipfile.is_zipfile(file_path):
        raise HWPXConversionError("Unsupported .hwpx format or corrupted file")

    with zipfile.ZipFile(file_path, "r") as zf:
        names = zf.namelist()
        section_paths = [
            n
            for n in names
            if n.lower().endswith(".xml") and "section" in n.lower() and "contents/" in n.lower()
        ]

        if not section_paths:
            raise HWPXConversionError("No section XML found in .hwpx file")

        section_paths.sort(key=_section_sort_key)
        pieces = []
        for path in section_paths:
            text = _extract_text_from_section_xml(zf.read(path))
            if text:
                pieces.append(text)

    markdown = "\n\n".join(pieces).strip()
    if not markdown:
        raise HWPXConversionError("No readable text found in .hwpx file")
    return markdown + "\n"

