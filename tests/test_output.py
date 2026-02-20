from pathlib import Path

import pytest

from gdrive_cli.output import render_records


def test_render_records_json():
    text = render_records([{"name": "x", "size": 1}], output_format="json")
    assert '"name": "x"' in text


def test_render_records_table():
    text = render_records([{"name": "sample.txt", "size": 10}], output_format="table")
    assert "name" in text
    assert "sample.txt" in text


def test_render_records_csv(tmp_path: Path):
    out = tmp_path / "rows.csv"
    msg = render_records([{"name": "hat", "size": 5}], output_format="csv", csv_path=str(out))
    assert "Wrote 1 row(s)" in msg
    assert out.exists()
    content = out.read_text(encoding="utf-8")
    assert "name,size" in content
    assert "hat,5" in content


def test_render_records_csv_requires_path():
    with pytest.raises(ValueError, match="csv_path"):
        render_records([{"name": "x"}], output_format="csv")
