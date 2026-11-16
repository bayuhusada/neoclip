"""Hook overlay: text wrapping, path safety and drawtext filter."""

from pathlib import Path

from app.core.config import settings
from app.services import hooks


def _use_tmp_storage(monkeypatch, tmp_path: Path) -> None:
    fonts = tmp_path / "fonts"
    fonts.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(settings, "storage_dir", tmp_path)
    monkeypatch.setattr(settings, "fonts_dir", fonts)


def test_empty_hook_writes_nothing(monkeypatch, tmp_path):
    _use_tmp_storage(monkeypatch, tmp_path)
    assert hooks.write_hook_text(1, "   \n  ") is None


def test_hook_text_is_wrapped_and_relative(monkeypatch, tmp_path):
    _use_tmp_storage(monkeypatch, tmp_path)
    rel = hooks.write_hook_text(
        7, "kalimat hook yang sangat panjang sekali sampai harus dibungkus jadi beberapa baris"
    )
    assert rel == "temp/hook_7.txt"
    lines = (tmp_path / rel).read_text(encoding="utf-8").splitlines()
    assert len(lines) > 1
    assert all(len(line) <= hooks.HOOK_MAX_LINE_CHARS for line in lines)
    assert len(lines) <= hooks.HOOK_MAX_LINES


def test_hook_filter_has_timing_and_centering():
    graph = hooks.build_hook_filter("temp/hook_3.txt", 2.5)
    assert graph.startswith(",drawtext=")
    assert "textfile=temp/hook_3.txt" in graph
    assert "between(t,0,2.50)" in graph
    assert "x=(w-text_w)/2" in graph


def test_hook_duration_is_clamped():
    assert "between(t,0,0.50)" in hooks.build_hook_filter("temp/hook_3.txt", -5)
    assert "between(t,0,10.00)" in hooks.build_hook_filter("temp/hook_3.txt", 99)


def test_missing_hook_returns_empty_filter():
    assert hooks.build_hook_filter(None, 3.0) == ""
