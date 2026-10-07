# DateiSortieren – lokaler Agent

Python-Daemon, der Ordner überwacht, Dateien per KI versteht, sortiert, umbenennt,
Duplikate findet, Medien komprimiert und aufräumt – mit Dry-Run und Undo.

Installation und Einrichtung: siehe [README im Hauptverzeichnis](../README.md).

```bash
pip install -e ".[anthropic]"
dateisortieren init
dateisortieren scan        # Vorschau
dateisortieren run         # Daemon
```
