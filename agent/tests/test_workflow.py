"""End-to-End: Planen (Dry-Run) -> Ausführen -> Rückgängig machen."""

from __future__ import annotations

from pathlib import Path

from conftest import INVOICE_TEXT, make_file
from PIL import Image

from dateisortieren.service import Agent


def test_dry_run_changes_nothing_then_apply_and_undo(cfg):
    d = cfg.watch_dirs[0]
    invoice = make_file(d / "SCAN_2026_09_12.txt", INVOICE_TEXT)
    agent = Agent(cfg)

    plan = agent.scan()
    assert invoice.exists(), "Dry-Run darf nichts verändern"
    moves = [a for a in plan.actions if a.kind == "move"]
    assert len(moves) == 1
    expected = cfg.target_root / "Finanzen" / "Rechnungen" / "2026" / "2026-09-12_Telekom_Rechnung_89Euro.txt"
    assert moves[0].dst == str(expected)

    # gleicher Scan erzeugt keine doppelten Vorschläge
    assert not [a for a in agent.scan().actions if a.kind == "move"]

    results = agent.apply_all_proposed(plan.batch_id)
    assert all(r.status == "applied" for r in results)
    assert expected.exists() and not invoice.exists()

    undone = agent.undo(plan.batch_id)
    assert all(r.status == "undone" for r in undone)
    assert invoice.exists() and not expected.exists()
    assert not (cfg.target_root / "Finanzen").exists(), "leere Zielordner werden beim Undo entfernt"


def test_exact_duplicates_keep_older_copy(cfg):
    d = cfg.watch_dirs[0]
    original = make_file(d / "Urlaub.txt", "gleicher Inhalt " * 20, age_hours=10)
    copy = make_file(d / "Urlaub (1).txt", "gleicher Inhalt " * 20)
    agent = Agent(cfg)
    plan = agent.scan()
    deletes = [a for a in plan.actions if a.kind == "delete"]
    assert [a.src for a in deletes] == [str(copy)]
    assert deletes[0].details["duplicate_of"] == str(original)

    agent.apply_ids([deletes[0].id])
    assert not copy.exists()
    backup = Path(agent.manifest.get(deletes[0].id).backup_path)
    assert backup.exists(), "Gelöschtes landet in der Quarantäne"
    agent.undo(deletes[0].id)
    assert copy.exists()


def test_auto_mode_respects_confidence_and_never_auto_deletes(cfg):
    cfg.dry_run = False
    d = cfg.watch_dirs[0]
    invoice = make_file(d / "scan001.txt", INVOICE_TEXT)
    installer = make_file(d / "setup.msi", age_hours=24 * 60)
    agent = Agent(cfg)
    agent.scan()
    assert installer.exists(), "Installer wird nur vorgeschlagen, nicht automatisch gelöscht"
    pending = agent.manifest.query(status="proposed")
    assert any(a.kind == "delete" and a.src == str(installer) for a in pending)
    # Eindeutige Rechnung (hohe Konfidenz) wird automatisch einsortiert
    assert not invoice.exists()
    assert any(cfg.target_root.rglob("*_Telekom_Rechnung_89Euro.txt"))


def test_image_compression_and_restore(cfg):
    cfg.media.enabled = True
    cfg.media.image_min_kb = 1
    cfg.organize.enabled = False
    cfg.rename.enabled = False
    d = cfg.watch_dirs[0]
    img_path = d / "foto.png"
    Image.effect_noise((400, 400), 60).convert("RGB").save(img_path, format="PNG", compress_level=0)
    original_bytes = img_path.read_bytes()
    cfg.media.png_lossy = True

    agent = Agent(cfg)
    plan = agent.scan()
    compress = [a for a in plan.actions if a.kind == "compress"]
    assert len(compress) == 1
    result = agent.apply_ids([compress[0].id])[0]
    assert result.status == "applied"
    assert img_path.stat().st_size < len(original_bytes)
    agent.undo(result.id)
    assert img_path.read_bytes() == original_bytes


def test_safelisted_file_is_never_touched(cfg):
    d = cfg.watch_dirs[0]
    secret = make_file(d / "tresor.kdbx", "x")
    cfg.safelist.extensions = [".kdbx"]
    agent = Agent(cfg)
    assert not [a for a in agent.scan().actions if a.src == str(secret)]


def test_user_rule_overrides_ai(cfg):
    cfg.rules = [{"name": "Telekom", "priority": 1, "match": {"content_keywords": ["telekom"]},
                  "target": "Verträge/Telekom/{year}", "tags": ["telekom"]}]
    d = cfg.watch_dirs[0]
    make_file(d / "scan_77.txt", INVOICE_TEXT)
    agent = Agent(cfg)
    move = [a for a in agent.scan().actions if a.kind == "move"][0]
    assert Path(move.dst).parent == cfg.target_root / "Verträge" / "Telekom" / "2026"
    assert "telekom" in move.tags


def test_duplicate_delete_follows_moved_original(cfg):
    """Original wird im selben Durchlauf einsortiert – das Duplikat darf trotzdem gelöscht werden."""
    d = cfg.watch_dirs[0]
    make_file(d / "scan0007.txt", INVOICE_TEXT, age_hours=48)
    copy = make_file(d / "scan0007 (1).txt", INVOICE_TEXT)
    agent = Agent(cfg)
    plan = agent.scan()
    assert {a.kind for a in plan.actions} == {"move", "delete"}
    results = agent.apply_all_proposed(plan.batch_id)
    assert all(r.status == "applied" for r in results), [r.error for r in results]
    assert not copy.exists()
    delete = next(r for r in results if r.kind == "delete")
    assert Path(delete.details["duplicate_of"]).parent.parent.parent.name == "Finanzen"


def test_undo_in_any_order_restores_compressed_and_moved_file(cfg):
    """Dashboard schickt Undo-Wünsche ungeordnet – Komprimierung + Verschiebung müssen trotzdem sauber zurück."""
    cfg.media.enabled = True
    cfg.media.image_min_kb = 1
    cfg.media.png_lossy = True
    d = cfg.watch_dirs[0]
    img = d / "foto.png"
    Image.effect_noise((300, 300), 60).convert("RGB").save(img, format="PNG", compress_level=0)
    original = img.read_bytes()
    agent = Agent(cfg)
    plan = agent.scan()
    results = agent.apply_all_proposed(plan.batch_id)
    assert {r.kind for r in results} == {"move", "compress"} and all(r.status == "applied" for r in results)
    move = next(r for r in results if r.kind == "move")
    compress = next(r for r in results if r.kind == "compress")
    # absichtlich falsche Reihenfolge: erst Verschiebung, dann Komprimierung
    assert agent.executor.undo(agent.manifest.get(move.id)).status == "undone"
    assert agent.executor.undo(agent.manifest.get(compress.id)).status == "undone"
    assert img.read_bytes() == original
