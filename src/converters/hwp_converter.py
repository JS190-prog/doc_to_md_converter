import re
import struct
import zlib


class HWPConversionError(Exception):
    pass


def _is_hwp_compressed(ole):
    try:
        header = ole.openstream("FileHeader").read()
    except Exception as exc:
        raise HWPConversionError("Invalid HWP file: missing FileHeader stream") from exc

    if len(header) < 37:
        raise HWPConversionError("Invalid HWP file: malformed FileHeader")

    # HWP 5.x property bit 0 indicates compressed body streams.
    return (header[36] & 0x01) == 0x01


def _section_stream_names(ole):
    names = []
    for entry in ole.listdir():
        if len(entry) == 2 and entry[0] == "BodyText" and entry[1].startswith("Section"):
            names.append(entry[1])
    if not names:
        raise HWPConversionError("No BodyText sections found in HWP file")

    def section_index(name):
        try:
            return int(name.replace("Section", ""))
        except Exception:
            return 10**9

    return sorted(names, key=section_index)


def _decompress_if_needed(data, compressed):
    if not compressed:
        return data
    try:
        # HWP uses raw DEFLATE for compressed record streams.
        return zlib.decompress(data, -15)
    except Exception:
        # Fallback for files packaged with zlib wrapper.
        return zlib.decompress(data)


def _extract_text_from_record_stream(data):
    pos = 0
    out = []

    while pos + 4 <= len(data):
        header = struct.unpack_from("<I", data, pos)[0]
        pos += 4

        rec_type = header & 0x3FF
        rec_len = (header >> 20) & 0xFFF
        if rec_len == 0xFFF:
            if pos + 4 > len(data):
                break
            rec_len = struct.unpack_from("<I", data, pos)[0]
            pos += 4

        if pos + rec_len > len(data):
            break

        payload = data[pos : pos + rec_len]
        pos += rec_len

        # 67: HWPTAG_PARA_TEXT
        if rec_type == 67 and payload:
            out.append(payload.decode("utf-16le", errors="ignore"))

    text = "".join(out)
    text = text.replace("\r", "\n").replace("\x00", "")
    text = re.sub(r"[\x01-\x08\x0b\x0c\x0e-\x1f]", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def convert_hwp_to_md(file_path):
    try:
        import olefile
    except ImportError as exc:
        raise ImportError("olefile is required for .hwp conversion") from exc

    if not olefile.isOleFile(file_path):
        raise HWPConversionError("Unsupported .hwp format or corrupted file")

    with olefile.OleFileIO(file_path) as ole:
        compressed = _is_hwp_compressed(ole)
        sections = _section_stream_names(ole)

        pieces = []
        for section_name in sections:
            raw = ole.openstream(["BodyText", section_name]).read()
            decoded = _decompress_if_needed(raw, compressed)
            text = _extract_text_from_record_stream(decoded)
            if text:
                pieces.append(text)

    markdown = "\n\n".join(pieces).strip()
    if not markdown:
        raise HWPConversionError("No readable text found in .hwp file")
    return markdown + "\n"

