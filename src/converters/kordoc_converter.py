"""kordoc CLI wrapper.

kordoc (https://github.com/chrisryugj/kordoc) is a Node.js based Korean
document parser with strong table reconstruction (merged cells, nested
tables) and deep HWP format coverage (HWP 3.x/5.x, HWPX, distribution HWP).
Installed globally via: npm install -g kordoc pdfjs-dist@5
(pdfjs-dist v6 is incompatible with kordoc 3.x — keep the v5 pin.)
"""

import logging
import os
import shutil
import subprocess
import tempfile
from urllib.parse import quote

logger = logging.getLogger(__name__)

_kordoc_cmd = None
_INSTALL_HINT = "npm install -g kordoc pdfjs-dist@5"


def _find_kordoc():
    """Locate the kordoc CLI shim, caching the result."""
    global _kordoc_cmd
    if _kordoc_cmd is not None:
        return _kordoc_cmd

    exe = shutil.which("kordoc") or shutil.which("kordoc.cmd")
    if exe is None:
        candidate = os.path.join(
            os.environ.get("APPDATA", ""), "npm", "kordoc.cmd"
        )
        if os.path.isfile(candidate):
            exe = candidate
    if exe is None:
        raise FileNotFoundError(
            f"kordoc CLI not found. Install with: {_INSTALL_HINT}"
        )
    _kordoc_cmd = exe
    return exe


def check_kordoc_dependency():
    """Return a non-raising status dict for startup/diagnostic checks."""
    status = {
        "available": False,
        "path": None,
        "version": None,
        "warning": None,
        "install_hint": _INSTALL_HINT,
    }

    try:
        exe = _find_kordoc()
    except FileNotFoundError as exc:
        status["warning"] = str(exc)
        return status

    status["available"] = True
    status["path"] = exe

    try:
        result = subprocess.run(
            [exe, "--version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
    except Exception as exc:
        status["warning"] = f"kordoc found, but version check failed: {exc}"
        return status

    output = (result.stdout or result.stderr or "").strip()
    if result.returncode == 0:
        status["version"] = output.splitlines()[0] if output else "unknown"
    else:
        status["warning"] = (
            f"kordoc found, but --version exited {result.returncode}: "
            f"{output[:300]}"
        )
    return status


def convert_with_kordoc(file_path, asset_origin=None):
    """Convert a document to markdown via the kordoc CLI.

    ``asset_origin`` is the path whose folder/stem should host extracted
    images (defaults to ``file_path``); pass the user's original document
    when ``file_path`` is a temporary intermediate.

    Returns the markdown string. Raises on CLI failure or empty output
    (e.g. scanned PDFs without a text layer) so router fallbacks engage.
    """
    exe = _find_kordoc()

    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = os.path.join(tmpdir, "kordoc_out.md")
        result = subprocess.run(
            [exe, os.path.abspath(file_path), "-o", out_path, "--silent"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
        )
        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            raise RuntimeError(f"kordoc failed (exit {result.returncode}): {stderr[:500]}")
        if not os.path.isfile(out_path):
            raise RuntimeError("kordoc produced no output file")
        with open(out_path, encoding="utf-8") as f:
            md = f.read()

        try:
            md = _preserve_extracted_assets(
                md, tmpdir, out_path, asset_origin or file_path
            )
        except OSError as exc:
            # Image export is best-effort; never lose the text because the
            # source folder is read-only or the disk is full.
            logger.warning("kordoc images could not be saved: %s", exc)

    if not md.strip():
        raise RuntimeError("kordoc produced empty output (image-based document?)")
    return md


def _preserve_extracted_assets(md, tmpdir, out_path, file_path):
    """Copy images kordoc extracted into the temp dir next to the source
    document (as <stem>_images/) and rewrite markdown links accordingly.
    kordoc emits bare `image_NNN.jpg` refs while writing the files into an
    `images/` subfolder, so both ref forms are rewritten."""
    assets = []
    for root, _dirs, files in os.walk(tmpdir):
        for name in files:
            full = os.path.join(root, name)
            if os.path.abspath(full) != os.path.abspath(out_path):
                assets.append(full)
    if not assets:
        return md

    src_path = os.path.abspath(file_path)
    stem = os.path.splitext(os.path.basename(src_path))[0]
    assets_dirname = f"{stem}_images"
    assets_dir = os.path.join(os.path.dirname(src_path), assets_dirname)
    os.makedirs(assets_dir, exist_ok=True)
    ref_dir = quote(assets_dirname)

    for full in assets:
        name = os.path.basename(full)
        shutil.copy2(full, os.path.join(assets_dir, name))
        md = md.replace(f"](images/{name})", f"]({ref_dir}/{name})")
        md = md.replace(f"]({name})", f"]({ref_dir}/{name})")
    return md
