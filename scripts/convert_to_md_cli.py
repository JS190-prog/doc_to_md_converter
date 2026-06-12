from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")

from src.backend import process_file  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Convert supported office documents to Markdown."
    )
    parser.add_argument("files", nargs="+", help="Input file paths to convert")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON results",
    )
    args = parser.parse_args()

    results = []
    exit_code = 0

    for raw_path in args.files:
        input_path = Path(raw_path).expanduser().resolve()
        if not input_path.exists():
            record = {
                "file": str(input_path),
                "success": False,
                "message": "File not found",
            }
            results.append(record)
            exit_code = 1
            continue

        success, message = process_file(str(input_path))
        output_path = str(input_path.with_suffix("")) + "_converted.md"
        record = {
            "file": str(input_path),
            "success": bool(success),
            "message": message,
            "output_path": output_path if success else None,
        }
        results.append(record)
        if not success:
            exit_code = 1

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        for item in results:
            status = "SUCCESS" if item["success"] else "FAILED"
            print(f"[{status}] {item['file']}")
            print(f"  message: {item['message']}")
            if item.get("output_path"):
                print(f"  output : {item['output_path']}")

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
