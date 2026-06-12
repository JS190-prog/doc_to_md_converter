"""kordoc CLI wrapper.

kordoc (https://github.com/chrisryugj/kordoc) is a Node.js based Korean
document parser with strong table reconstruction (merged cells, nested
tables) and deep HWP format coverage (HWP 3.x/5.x, HWPX, distribution HWP).
Installed globally via: npm install -g kordoc pdfjs-dist@5
(pdfjs-dist v6 is incompatible with kordoc 3.x — keep the v5 pin.)
"""

import os
import shutil
import subprocess
import tempfile
from urllib.parse import quote

_kordoc_cmd = None


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
            "kordoc CLI not found. Install with: npm install -g kordoc pdfjs-dist@5"
        )
    _kordoc_cmd = exe
    return exe


def convert_with_kordoc(file_path):
    """Convert a document to markdown via the kordoc CLI.

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

        md = _preserve_extracted_assets(md, tmpdir, out_path, file_path)

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
