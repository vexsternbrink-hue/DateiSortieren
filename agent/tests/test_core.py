from __future__ import annotations

from datetime import datetime
from pathlib import Path

from conftest import INVOICE_TEXT, make_file

from dateisortieren import cleanup
from dateisortieren.ai.heuristic import find_amount, find_date
from dateisortieren.models import Classification
from dateisortieren.renamer import build_filename, build_target_dir, is_cryptic, unique_path
from dateisortieren.rules import matches
from dateisortieren.safelist import IGNORE_MARKER, SafeList


def test_cryptic_names():
    assert is_cryptic("SCAN_2026_09_12.pdf")
    assert is_cryptic("IMG_1234.jpg")
    assert is_cryptic("download (3).pdf")
    assert is_cryptic("3f2b9c1e-1a2b-4c3d-9e8f-0123456789ab.pdf")
    assert not is_cryptic("Mietvertrag Wohnung Berlin.pdf")
    assert not is_cryptic("2026-09-12_Telekom_Rechnung_89Euro.pdf")


def test_build_filename_matches_example():
    c = Classification(category="Finanzen/Rechnungen", doc_type="Rechnung", vendor="Telekom",
                       date="2026-09-12", amount=89.0, currency="EUR")
    name = build_filename(c, "{date}_{vendor}_{doc_type}_{amount}", Path("SCAN_2026_09_12.PDF"), datetime(2026, 1, 1))
    assert name == "2026-09-12_Telekom_Rechnung_89Euro.pdf"


def test_build_filename_cents_and_missing_fields():
    c = Classification(category="X", doc_type="Quittung", amount=12.5, currency="EUR")
    name = build_filename(c, "{date}_{vendor}_{doc_type}_{amount}", Path("a.pdf"), datetime(2026, 3, 4))
    assert name == "2026-03-04_Quittung_12,50Euro.pdf"


def test_target_dir_sanitizes(tmp_path: Path):
    c = Classification(category="Finanzen/../Rechnungen", date="2025-01-31")
    target = build_target_dir(c, "{category}/{year}", tmp_path, datetime(2026, 1, 1))
    assert target == tmp_path / "Finanzen" / "Rechnungen" / "2025"


def test_unique_path_never_overwrites(tmp_path: Path):
    existing = make_file(tmp_path / "a.pdf")
    assert unique_path(existing) == tmp_path / "a (1).pdf"


def test_date_and_amount_extraction():
    assert find_date("SCAN_2026_09_12") == "2026-09-12"
    assert find_date("Rechnungsdatum 12.09.2026") == "2026-09-12"
    assert find_date("vom 3. März 2025") == "2025-03-03"
    assert find_amount(INVOICE_TEXT) == (89.0, "EUR")
    assert find_amount("Summe 1.234,56 EUR")[0] == 1234.56


def test_cleanup_detection(cfg):
    d = cfg.watch_dirs[0]
    old_installer = make_file(d / "setup.exe", age_hours=24 * 30)
    new_installer = make_file(d / "fresh.dmg")
    partial = make_file(d / "film.mp4.crdownload", age_hours=72)
    temp = make_file(d / "~$bericht.docx")
    assert cleanup.classify_file(old_installer, cfg).category == "installer"
    assert cleanup.classify_file(new_installer, cfg) is None
    assert cleanup.classify_file(partial, cfg).category == "incomplete"
    assert cleanup.classify_file(make_file(d / ".DS_Store"), cfg).category == "temp"
    assert cleanup.classify_file(temp, cfg) is None  # zu jung
    (d / "leer" / "auch_leer").mkdir(parents=True)
    empties = cleanup.find_empty_dirs(d, cfg)
    assert [e.path.name for e in empties] == ["leer"]


def test_safelist(cfg):
    d = cfg.watch_dirs[0]
    cfg.safelist.paths = [str(d / "Projekte")]
    cfg.safelist.extensions = ["kdbx"]
    cfg.safelist.globs = ["Steuer_*"]
    sl = SafeList(cfg)
    assert sl.is_protected(d / "Projekte" / "x.pdf")
    assert sl.is_protected(d / "passwords.kdbx")
    assert sl.is_protected(d / "Steuer_2025.pdf")
    assert sl.is_protected(cfg.state_dir / "manifest.db")
    assert not sl.is_protected(d / "rechnung.pdf")
    make_file(d / "privat" / IGNORE_MARKER)
    assert sl.is_protected(d / "privat" / "bild.jpg")


def test_rule_matching(tmp_path: Path):
    rule = {"name": "Telekom", "match": {"extensions": ["pdf"], "content_keywords": ["telekom"]}}
    assert matches(rule, tmp_path / "a.pdf", INVOICE_TEXT, 100)
    assert not matches(rule, tmp_path / "a.txt", INVOICE_TEXT, 100)
    assert not matches({"name": "leer", "match": {}}, tmp_path / "a.pdf", "", 1)
    cat_rule = {"match": {"category_is": "Finanzen"}}
    assert matches(cat_rule, tmp_path / "a.pdf", "", 1, "Finanzen/Rechnungen")
    assert not matches(cat_rule, tmp_path / "a.pdf", "", 1, "Verträge")
