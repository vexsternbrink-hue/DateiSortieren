"""Kommandozeile: dateisortieren <befehl>"""

from __future__ import annotations

import argparse
import logging
import os
import shutil
import sys
from pathlib import Path

from rich.console import Console
from rich.table import Table

from . import __version__
from .config import DEFAULT_CONFIG_PATH, load_config
from .models import Action

console = Console()
EXAMPLE_CONFIG = Path(__file__).resolve().parent / "data" / "config.example.yaml"

STATUS_STYLE = {"proposed": "yellow", "approved": "cyan", "applied": "green", "undone": "magenta",
                "failed": "red", "rejected": "dim", "skipped": "dim", "undo_requested": "magenta"}
KIND_LABEL = {"move": "Sortieren", "delete": "Löschen*", "compress": "Komprimieren"}


def _agent(args):
    from .service import Agent

    cfg = load_config(Path(args.config) if args.config else None)
    if getattr(args, "dirs", None):
        cfg.watch_dirs = [Path(d).expanduser().resolve() for d in args.dirs]
    agent = Agent(cfg)
    if not getattr(args, "offline", False):
        agent.sync_config()
    return agent


def _short(path: str | None, width: int = 60) -> str:
    if not path:
        return ""
    home = str(Path.home())
    p = path.replace(home, "~", 1) if path.startswith(home) else path
    return p if len(p) <= width else "…" + p[-(width - 1):]


def print_actions(actions: list[Action], title: str) -> None:
    table = Table(title=title, show_lines=False, header_style="bold")
    table.add_column("ID", style="dim", no_wrap=True)
    table.add_column("Aktion")
    table.add_column("Status")
    table.add_column("Quelle")
    table.add_column("Ziel / Grund")
    table.add_column("Sicherheit", justify="right")
    for a in actions:
        target = _short(a.dst) if a.kind == "move" else a.reason
        if a.error:
            target += f"\n[red]{a.error}[/red]"
        table.add_row(a.id[:8], KIND_LABEL.get(a.kind, a.kind), f"[{STATUS_STYLE.get(a.status, '')}]{a.status}[/]",
                      _short(a.src), target, f"{a.confidence:.0%}")
    console.print(table)
    if any(a.kind == "delete" for a in actions):
        console.print("[dim]* Löschen = Verschieben in die Quarantäne (wiederherstellbar per 'undo').[/dim]")


def cmd_init(args) -> int:
    target = Path(args.config).expanduser() if args.config else DEFAULT_CONFIG_PATH
    if target.exists() and not args.force:
        console.print(f"[yellow]Konfiguration existiert bereits:[/] {target} (überschreiben mit --force)")
        return 1
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(EXAMPLE_CONFIG, target)
    console.print(f"[green]✓[/] Konfiguration angelegt: {target}\n  Passe watch_dirs, target_root und ai.provider an.")
    return 0


def cmd_scan(args) -> int:
    agent = _agent(args)
    if args.apply:
        agent.cfg.dry_run = False
    plan = agent.scan()
    print_actions(plan.actions, f"Plan {plan.batch_id[:8]} – {len(plan)} Aktionen "
                                f"({'Dry-Run' if agent.cfg.dry_run else 'ausgeführt, sofern sicher'})")
    if agent.cfg.dry_run and plan.actions:
        console.print(f"\nAusführen: [bold]dateisortieren apply --batch {plan.batch_id}[/] "
                      "oder im Web-Dashboard unter 'Vorschau' freigeben.")
    return 0


def cmd_pending(args) -> int:
    agent = _agent(args)
    print_actions(agent.manifest.query(status=["proposed", "approved"], limit=args.limit), "Offene Vorschläge (Dry-Run)")
    return 0


def cmd_apply(args) -> int:
    agent = _agent(args)
    if args.ids:
        ids = [_resolve_id(agent, i) for i in args.ids]
        results = agent.apply_ids([i for i in ids if i])
    elif args.all or args.batch:
        results = agent.apply_all_proposed(args.batch)
    else:
        console.print("Bitte IDs, --batch <id> oder --all angeben.")
        return 2
    print_actions(results, "Ausgeführt")
    return 0 if all(r.status != "failed" for r in results) else 1


def cmd_history(args) -> int:
    agent = _agent(args)
    print_actions(agent.manifest.query(status=["applied", "undone", "failed", "skipped"], limit=args.limit), "Verlauf")
    return 0


def cmd_undo(args) -> int:
    agent = _agent(args)
    target = _resolve_id(agent, args.target) if args.target else None
    results = agent.undo(target or args.target)
    if not results:
        console.print("Nichts zum Rückgängigmachen gefunden.")
        return 1
    print_actions(results, "Rückgängig gemacht")
    return 0 if all(r.status == "undone" for r in results) else 1


def cmd_classify(args) -> int:
    agent = _agent(args)
    path = Path(args.file).expanduser().resolve()
    result = agent.classifier.classify(path)
    c = result.classification
    table = Table(title=path.name, show_header=False)
    for key, value in c.to_dict().items():
        table.add_row(key, str(value))
    console.print(table)
    actions = agent.planner.plan_file(path)
    if actions:
        print_actions(actions, "Würde ausgeführt werden (nicht gespeichert)")
    return 0


def cmd_run(args) -> int:
    from .watcher import Daemon

    agent = _agent(args)
    Daemon(agent).run()
    return 0


def cmd_sync(args) -> int:
    agent = _agent(args)
    if not agent.cloud:
        console.print("[red]Kein Dashboard konfiguriert[/] (cloud.api_url / cloud.agent_token)")
        return 1
    from .sync import CloudError

    try:
        reply = agent.cloud.heartbeat({"stats": agent.manifest.stats()})
    except CloudError as exc:
        console.print(f"[red]{exc}[/]")
        return 1
    if reply.get("scan_requested"):
        plan = agent.scan()
        console.print(f"Scan (im Dashboard angefordert): {len(plan)} Vorschläge")
    stats = agent.process_commands()
    agent.push()
    console.print(f"[green]✓[/] Synchronisiert – {stats['applied']} ausgeführt, {stats['undone']} rückgängig, "
                  f"{stats['failed']} Fehler")
    return 0 if stats["failed"] == 0 else 1


def cmd_purge(args) -> int:
    agent = _agent(args)
    console.print(f"{agent.executor.purge_trash()} Quarantäne-Einträge endgültig gelöscht.")
    return 0


def cmd_doctor(args) -> int:
    from .extract import ocr_available
    from .media import ffmpeg_available

    cfg = load_config(Path(args.config) if args.config else None)
    checks = [
        ("Konfiguration", DEFAULT_CONFIG_PATH.exists() or bool(args.config), str(args.config or DEFAULT_CONFIG_PATH)),
        ("Überwachte Ordner", all(d.exists() for d in cfg.watch_dirs), ", ".join(map(str, cfg.watch_dirs))),
        ("Zielordner", True, str(cfg.target_root)),
        ("KI-Provider", True, cfg.ai.provider),
        ("ANTHROPIC_API_KEY", cfg.ai.provider != "anthropic" or bool(os.environ.get("ANTHROPIC_API_KEY")), "gesetzt" if os.environ.get("ANTHROPIC_API_KEY") else "fehlt"),
        ("OPENAI_API_KEY", cfg.ai.provider != "openai" or bool(os.environ.get("OPENAI_API_KEY")), "gesetzt" if os.environ.get("OPENAI_API_KEY") else "fehlt"),
        ("OCR (tesseract)", ocr_available() or not cfg.ocr.enabled, "verfügbar" if ocr_available() else "nicht installiert"),
        ("ffmpeg (Videos)", ffmpeg_available() or not cfg.media.enabled, "verfügbar" if ffmpeg_available() else "nicht installiert"),
        ("Dashboard-Verbindung", True, cfg.cloud.api_url or "nicht konfiguriert (nur lokal)"),
        ("Modus", True, "Dry-Run" if cfg.dry_run else "Automatisch"),
    ]
    if cfg.cloud.api_url and cfg.cloud.agent_token:
        from .sync import CloudClient, CloudError

        try:
            CloudClient(cfg).heartbeat()
            checks.append(("Dashboard erreichbar", True, "OK"))
        except CloudError as exc:
            checks.append(("Dashboard erreichbar", False, str(exc)))
    table = Table(title=f"dateisortieren {__version__} – Systemcheck", show_header=False)
    for name, ok, info in checks:
        table.add_row("[green]✓[/]" if ok else "[red]✗[/]", name, info)
    console.print(table)
    return 0 if all(ok for _n, ok, _i in checks) else 1


def _resolve_id(agent, prefix: str) -> str | None:
    """Erlaubt kurze IDs (die ersten 8 Zeichen) wie in der Tabelle angezeigt."""
    if agent.manifest.get(prefix):
        return prefix
    rows = agent.manifest._conn.execute(  # noqa: SLF001
        "SELECT id FROM actions WHERE id LIKE ? UNION SELECT batch_id FROM actions WHERE batch_id LIKE ? LIMIT 2",
        (prefix + "%", prefix + "%"),
    ).fetchall()
    return rows[0][0] if len(rows) == 1 else None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dateisortieren", description="KI-gestützte Datei-Organisation")
    parser.add_argument("--config", help="Pfad zur config.yaml")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init", help="Beispiel-Konfiguration anlegen")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("scan", help="Ordner analysieren (Dry-Run-Vorschau)")
    p.add_argument("dirs", nargs="*", help="Ordner (Standard: watch_dirs)")
    p.add_argument("--apply", action="store_true", help="Sichere Aktionen direkt ausführen")
    p.add_argument("--offline", action="store_true", help="Ohne Dashboard-Sync")
    p.set_defaults(func=cmd_scan)

    p = sub.add_parser("pending", help="Offene Vorschläge anzeigen")
    p.add_argument("--limit", type=int, default=200)
    p.set_defaults(func=cmd_pending)

    p = sub.add_parser("apply", help="Vorschläge ausführen")
    p.add_argument("ids", nargs="*")
    p.add_argument("--batch")
    p.add_argument("--all", action="store_true")
    p.set_defaults(func=cmd_apply)

    p = sub.add_parser("history", help="Verlauf anzeigen")
    p.add_argument("--limit", type=int, default=100)
    p.set_defaults(func=cmd_history)

    p = sub.add_parser("undo", help="Aktion oder Batch rückgängig machen (Standard: letzter Batch)")
    p.add_argument("target", nargs="?")
    p.set_defaults(func=cmd_undo)

    p = sub.add_parser("classify", help="Eine Datei testweise klassifizieren")
    p.add_argument("file")
    p.add_argument("--offline", action="store_true")
    p.set_defaults(func=cmd_classify)

    p = sub.add_parser("run", help="Daemon starten (Watcher + Dashboard-Sync)")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("sync", help="Einmalig mit dem Dashboard synchronisieren (Freigaben/Undo ausführen)")
    p.set_defaults(func=cmd_sync)

    p = sub.add_parser("purge-trash", help="Abgelaufene Quarantäne-Einträge endgültig löschen")
    p.set_defaults(func=cmd_purge)

    p = sub.add_parser("doctor", help="Installation prüfen")
    p.set_defaults(func=cmd_doctor)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
    )
    for noisy in ("httpx", "anthropic", "openai", "watchdog", "PIL"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
