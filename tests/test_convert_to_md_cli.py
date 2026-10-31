from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


@pytest.fixture
def cli():
    path = Path(__file__).resolve().parents[1] / "scripts" / "convert_to_md_cli.py"
    spec = importlib.util.spec_from_file_location("convert_to_md_cli", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("success", [True, False])
def test_json_keeps_conversion_diagnostics_on_stderr(cli, monkeypatch, tmp_path, capsys, success):
    source = tmp_path / "example.docx"
    source.write_bytes(b"fixture")

    def convert(path):
        print("[engine] conversion progress")
        return success, "converted" if success else "conversion failed"

    monkeypatch.setattr(cli, "process_file", convert)
    monkeypatch.setattr(sys, "argv", ["convert_to_md_cli.py", "--json", str(source)])

    assert cli.main() == (0 if success else 1)
    output = capsys.readouterr()
    result = json.loads(output.out)
    assert result[0]["success"] is success
    assert "[engine] conversion progress" in output.err


def test_text_output_preserves_conversion_diagnostics(cli, monkeypatch, tmp_path, capsys):
    source = tmp_path / "example.docx"
    source.write_bytes(b"fixture")

    def convert(path):
        print("[engine] conversion progress")
        return True, "converted"

    monkeypatch.setattr(cli, "process_file", convert)
    monkeypatch.setattr(sys, "argv", ["convert_to_md_cli.py", str(source)])

    assert cli.main() == 0
    output = capsys.readouterr()
    assert "[engine] conversion progress" in output.out
    assert "[SUCCESS]" in output.out
    assert not output.err


def test_json_converts_a_real_document(cli, monkeypatch, tmp_path, capsys):
    from docx import Document

    source = tmp_path / "example.docx"
    document = Document()
    sentence = "A synthetic document verifies that conversion output stays machine readable."
    document.add_paragraph(sentence)
    document.save(source)
    monkeypatch.setattr(sys, "argv", ["convert_to_md_cli.py", "--json", str(source)])

    assert cli.main() == 0
    result = json.loads(capsys.readouterr().out)
    assert result[0]["success"] is True
    output = Path(result[0]["output_path"])
    assert sentence in output.read_text(encoding="utf-8")
