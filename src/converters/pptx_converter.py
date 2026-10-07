from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from typing import Iterable
from urllib.parse import quote

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE

logger = logging.getLogger(__name__)


@dataclass
class PptxAssetPaths:
    output_path: str
    assets_dir: str
    assets_ref_dir: str


def convert_pptx_to_md(file_path: str, output_path: str | None = None) -> str:
    """Convert PPTX to Markdown while preserving visual slides as PNG assets.

    PowerPoint slides contain many visual constructs that Markdown cannot
    represent faithfully. This converter therefore writes each slide as an
    image when PowerPoint automation is available, and also extracts searchable
    text, tables, notes, and embedded pictures with python-pptx.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    paths = _build_asset_paths(file_path, output_path)
    os.makedirs(paths.assets_dir, exist_ok=True)

    prs = Presentation(file_path)
    rendered_slides = _try_export_slides_with_powerpoint(file_path, paths.assets_dir, len(prs.slides))
    embedded_images = _extract_embedded_images(prs, paths.assets_dir)

    parts: list[str] = [f"# {os.path.splitext(os.path.basename(file_path))[0]}", ""]
    if not rendered_slides:
        parts.extend(
            [
                "> Slide preview images could not be rendered on this system.",
                "> Text, tables, and embedded pictures were extracted from the PPTX package.",
                "",
            ]
        )

    for slide_index, slide in enumerate(prs.slides, start=1):
        parts.extend([f"## Slide {slide_index}", ""])

        rendered = rendered_slides.get(slide_index)
        if rendered:
            parts.extend([f"![Slide {slide_index}]({_asset_ref(paths, rendered)})", ""])

        title = _slide_title(slide)
        if title:
            parts.extend([f"### {title}", ""])

        text_blocks = _collect_text_blocks(slide.shapes, excluded_texts={title} if title else set())
        if text_blocks:
            parts.extend(["### Extracted Text", ""])
            parts.extend(text_blocks)
            parts.append("")

        tables = _collect_tables(slide.shapes)
        if tables:
            parts.extend(["### Tables", ""])
            for table_md in tables:
                parts.extend([table_md, ""])

        slide_images = embedded_images.get(slide_index, [])
        if slide_images:
            parts.extend(["### Embedded Images", ""])
            for image_path in slide_images:
                alt = os.path.splitext(os.path.basename(image_path))[0].replace("_", " ")
                parts.extend([f"![{alt}]({_asset_ref(paths, image_path)})", ""])

        notes = _extract_notes(slide)
        if notes:
            parts.extend(["### Speaker Notes", "", notes, ""])

    try:
        os.rmdir(paths.assets_dir)  # only succeeds when nothing was written
    except OSError:
        pass

    return "\n".join(parts).rstrip() + "\n"


def _build_asset_paths(file_path: str, output_path: str | None) -> PptxAssetPaths:
    src_path = os.path.abspath(file_path)
    if output_path:
        md_path = os.path.abspath(output_path)
    else:
        base_name = os.path.splitext(src_path)[0]
        md_path = f"{base_name}_converted.md"

    stem = os.path.splitext(os.path.basename(src_path))[0]
    assets_dirname = f"{stem}_assets"
    assets_dir = os.path.join(os.path.dirname(md_path), assets_dirname)
    return PptxAssetPaths(
        output_path=md_path,
        assets_dir=assets_dir,
        assets_ref_dir=quote(assets_dirname),
    )


def _try_export_slides_with_powerpoint(file_path: str, assets_dir: str, slide_count: int) -> dict[int, str]:
    rendered: dict[int, str] = {}
    powerpoint = None
    presentation = None

    try:
        import win32com.client as win32

        powerpoint = win32.DispatchEx("PowerPoint.Application")
        presentation = powerpoint.Presentations.Open(
            os.path.abspath(file_path),
            ReadOnly=True,
            Untitled=False,
            WithWindow=False,
        )

        slide_width = float(presentation.PageSetup.SlideWidth)
        slide_height = float(presentation.PageSetup.SlideHeight)
        export_width = 1920
        export_height = max(1, int(round(export_width * slide_height / slide_width)))

        for slide_index in range(1, slide_count + 1):
            image_path = os.path.join(assets_dir, f"slide_{slide_index:03d}.png")
            presentation.Slides(slide_index).Export(image_path, "PNG", export_width, export_height)
            if os.path.isfile(image_path):
                rendered[slide_index] = image_path
    except Exception as exc:
        logger.info("pptx slide render skipped (PowerPoint unavailable): %s", exc)
    finally:
        if presentation is not None:
            try:
                presentation.Close()
            except Exception:
                pass
        if powerpoint is not None:
            try:
                powerpoint.Quit()
            except Exception:
                pass

    return rendered


def _extract_embedded_images(prs: Presentation, assets_dir: str) -> dict[int, list[str]]:
    extracted: dict[int, list[str]] = {}

    for slide_index, slide in enumerate(prs.slides, start=1):
        image_paths: list[str] = []
        for picture_index, shape in enumerate(_iter_shapes(slide.shapes), start=1):
            if shape.shape_type != MSO_SHAPE_TYPE.PICTURE:
                continue
            try:
                image = shape.image
                ext = (image.ext or "png").lower()
                image_path = os.path.join(
                    assets_dir,
                    f"slide_{slide_index:03d}_image_{picture_index:03d}.{ext}",
                )
                with open(image_path, "wb") as f:
                    f.write(image.blob)
                image_paths.append(image_path)
            except Exception as exc:
                logger.warning("pptx image extraction failed on slide %d: %s", slide_index, exc)
        if image_paths:
            extracted[slide_index] = image_paths

    return extracted


def _reading_order(shapes):
    """Top-to-bottom, left-to-right; shapes without geometry keep their order."""
    return sorted(
        shapes,
        key=lambda sh: (getattr(sh, "top", None) or 0, getattr(sh, "left", None) or 0),
    )


def _iter_shapes(shapes) -> Iterable:
    for shape in _reading_order(shapes):
        yield shape
        if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
            yield from _iter_shapes(shape.shapes)


def _slide_title(slide) -> str:
    title_shape = getattr(slide.shapes, "title", None)
    if title_shape is None:
        return ""
    return _clean_text(getattr(title_shape, "text", ""))


def _collect_text_blocks(shapes, excluded_texts: set[str] | None = None) -> list[str]:
    blocks: list[str] = []
    excluded_texts = excluded_texts or set()

    for shape in _iter_shapes(shapes):
        if getattr(shape, "has_table", False):
            continue
        if not getattr(shape, "has_text_frame", False):
            continue

        lines: list[str] = []
        for paragraph in shape.text_frame.paragraphs:
            text = _clean_text("".join(run.text for run in paragraph.runs) or paragraph.text)
            if not text:
                continue
            prefix = "  " * max(0, paragraph.level)
            bullet = "- " if paragraph.level > 0 else ""
            lines.append(f"{prefix}{bullet}{text}")

        block = "\n".join(lines).strip()
        if block and block not in excluded_texts and block not in blocks:
            blocks.append(block)

    return blocks


def _collect_tables(shapes) -> list[str]:
    tables: list[str] = []

    for shape in _iter_shapes(shapes):
        if not getattr(shape, "has_table", False):
            continue

        rows = []
        for row in shape.table.rows:
            rows.append([_clean_text(cell.text) for cell in row.cells])
        if not rows:
            continue

        max_cols = max(len(row) for row in rows)
        normalized_rows = [row + [""] * (max_cols - len(row)) for row in rows]
        header = normalized_rows[0]
        body = normalized_rows[1:] or [[""] * max_cols]
        table_lines = [
            "| " + " | ".join(_escape_table_cell(cell) for cell in header) + " |",
            "| " + " | ".join("---" for _ in header) + " |",
        ]
        for row in body:
            table_lines.append("| " + " | ".join(_escape_table_cell(cell) for cell in row) + " |")
        tables.append("\n".join(table_lines))

    return tables


def _extract_notes(slide) -> str:
    # has_notes_slide avoids python-pptx creating an empty notes slide.
    if not getattr(slide, "has_notes_slide", False):
        return ""
    text_frame = slide.notes_slide.notes_text_frame
    if text_frame is None:
        return ""

    paragraphs: list[str] = []
    for shape in text_frame.paragraphs:
        text = _clean_text(shape.text)
        if text:
            paragraphs.append(text)
    return "\n\n".join(paragraphs)


def _asset_ref(paths: PptxAssetPaths, asset_path: str) -> str:
    try:
        rel = os.path.relpath(asset_path, os.path.dirname(paths.output_path))
    except ValueError:
        rel = os.path.join(paths.assets_ref_dir, os.path.basename(asset_path))
    rel = rel.replace("\\", "/")
    return quote(rel, safe="/%._-")


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _escape_table_cell(text: str) -> str:
    return _clean_text(text).replace("|", "\\|")
