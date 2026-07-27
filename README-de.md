# TypoCompiler

**Sprachen:** [简体中文](./README.md) · [English](./README-en.md) · [日本語](./README-ja.md) · [한국어](./README-ko.md) · [Español](./README-es.md) · **Deutsch** · [Français](./README-fr.md)

TypoCompiler ist ein Desktop-Client, der Probleme in natürlicher Sprache wie Compilerdiagnosen darstellt. Editor, Diagnoseliste mit Quellpositionen und schreibgeschützte Ausgabe im Python-, Java- oder C++-Stil befinden sich in einem Fenster. Das Modell erkennt die Eingabesprache; die Qualität hängt jedoch vom konfigurierten Modell ab und eine vollständige Fehlererkennung ist nicht garantiert.

## Funktionen

- Das LLM liefert ausschließlich strukturierte JSON-Diagnosen; Zeilen, Spalten und Schweregrade werden lokal geprüft.
- Ein einziger canonical Diagnosesatz speist die deterministischen Python-, Java- und C++-Renderer.
- Ein Doppelklick springt zur Fundstelle; Ergebnisse für einen älteren Textstand werden als veraltet markiert.
- UTF-8-BOM und Zeilenenden bleiben erhalten, Konfiguration und Dokumente werden atomar gespeichert.
- Hintergrundaufgaben liefern Daten über eine Queue an den Tk-Hauptthread; alte Ergebnisse und Rückgaben nach dem Schließen werden ignoriert.

## Voraussetzungen und Start

- Python 3.10 oder neuer
- Tkinter (unter Windows und macOS üblicherweise enthalten; unter Linux eventuell `python3-tk`)
- Ein OpenAI-Chat-Completions-kompatibler Endpunkt und ein Modell

Es gibt keine zusätzlichen Python-Laufzeitabhängigkeiten.

```bash
python typocompiler.py
python -m typocompiler

# Installierter GUI-Befehl
python -m pip install .
typocompiler
```

Server und Modell werden unter **Einstellungen → LLM-Einstellungen** gesetzt; `F5` startet die Analyse. `Esc` verwirft das aktive Ergebnis, kann aber einen bereits gesendeten HTTP-Aufruf nicht zwingend beenden.

## Sicherheit, Datenschutz und Konfiguration

- Jede Analyse sendet den aktuellen Text und die Prüfanweisung an den konfigurierten Anbieter. Vertrauliche Texte gehören nur zu einem vertrauenswürdigen Dienst.
- Entfernte Endpunkte müssen HTTPS verwenden. Unverschlüsseltes HTTP ist nur für `localhost`, `127.0.0.1` und `::1` zulässig; Weiterleitungen sind deaktiviert.
- Bei Auswahl von `TYPOCOMPILER_API_KEY` wird kein Schlüssel lokal gespeichert. Lokale Speicherung schreibt ihn als Klartext nach `~/.typocompiler/config.json`.
- Eine beschädigte Konfiguration wird in eine eindeutige Datei `config.json.broken-*` verschoben, ohne ältere Belege absichtlich zu überschreiben; soweit möglich gelten nur Besitzerrechte.
- Ein UTF-8-Analysetext ist auf 2 MiB begrenzt; normale und Fehlerantworten sind ebenfalls größenbegrenzt und unterliegen einer Gesamtfrist. Als Token-Feld stehen das kompatible `max_tokens` und das neuere `max_completion_tokens` zur Auswahl.

## Diagnosen und eigene Profile

Leere, verweigerte oder abgeschnittene Antworten, ungültiges JSON und Positionen außerhalb des Textes werden nach dem Fail-Closed-Prinzip abgelehnt. Eigene Anweisungen dürfen nur `{input_text}` und `{style_name}` verwenden. Attribut- oder Indexzugriffe, unbekannte Felder und unvollständige Klammern werden vor dem Speichern abgewiesen. Ein anderer Anzeigestil rendert denselben Diagnosesatz nur lokal neu.

## Entwicklung

```bash
python -m pip install -e ".[dev]"
ruff check .
ruff format --check .
python -m pip wheel . --no-deps -w dist-test
```

Die CI prüft Ruff, Formatierung, Wheel-Build und Import. Lizenz: [MIT](./LICENSE).
