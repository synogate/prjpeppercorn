# CPE-Validierung: Test-Harness

Zweck: Verhalten eines einzelnen CPE (Carry/Propagate-Linien, Funktionsmodi, Config-Bits) auf dem echten GateMate messen und gegen
`schematics/cpe/sim/cpe.v` und das Schematic prüfen. Das Verfahren stammt aus den Messungen M00 ... M15 in `schematics/cpe/sim/hw_measurements.md`
(dort stehen Ergebnisse, Rohdaten und der Plan; hier steht, wie man misst).

Aufbau (Board, Scope, Toolchain) und Regeln für Experimente: `../lab.md` und `../README.md`.

## Inhalt

| Pfad | Inhalt |
|---|---|
| `rig.py` | Patchen von Config-Worten in `bitfile.txt`, Packen, Laden, UART-Zeile über das Scope lesen, Dekodieren. Kommandozeile und Bibliothek |
| `base/` | Baseline-Design (`top.v`, `Makefile`, `pins.ccf`, `top.sdc`): ein `CC_ADDF` mit allen 8 Eingangskombinationen, Ausgabe über UART |
| `experiments/batch1.py` ... `batch6.py` | Die Messreihen M10 ... M15 (`COUTX`, `CINX`, `CINY1`, `CINY2`), als Vorlage für neue Reihen |
| `data/results1.json` ... `results6.json` | Rohdaten dieser Reihen (Zeile des Testdesigns und `B'(B)` je Konfiguration) |
| `make_tb_coutx.py` | Erzeugt `schematics/cpe/sim/tb_coutx.v` aus `data/results1..5.json` (Regressionstest der Messungen gegen `cpe.v`) |
| `truth_rig/` | Zweiter Aufbau (Methode B): Referenztakt auf `UART0_TX`, orthogonale 50-%-Signale an allen Eingängen, Messpin `UART0_RX`, eine Messung = vollständige Wahrheitstabelle (siehe `truth_rig/README.md`) |

## Regel: `lab/` bleibt sauber

Der Harness schreibt **nichts** nach `lab/`. Arbeitsordner ist `CPE_RIG_WORK` (Standard `%TEMP%\cpe_rig_work`): dort liegen die gebaute Baseline
(`base/`), jede gepatchte Variante (`NAME.txt`, `NAME.bit`) und die Ergebnisdateien der Reihen (`resultsN.json`). Der Harness selbst wird nur auf
ausdrücklichen Wunsch des Nutzers geändert. Messdaten, die man behalten will, werden bewusst nach `data/` kopiert.

## Schnellstart

Alle Befehle mit absolutem Pfad und ohne `PATH` zu verändern (nextpnr kommt aus dem Entwickler-Build, siehe Fallstricke).

    cd /c/Users/mio/source/prjpeppercorn/lab/cpe_rig
    python rig.py setup                         # Baseline bauen (einmal, ca. 1 min)
    python rig.py base0                         # ungepatcht laden und lesen: erwartet B'(B) = {0: 0, 1: 1}
    python rig.py t1 146:19:C_CX_I=-            # Testobjekt-CPE X146Y19: Wort C_CX_I löschen (0), dann messen
    python rig.py t2 146:19:C_FUNCTION=001 146:19:C_HORIZ=1
    python experiments/batch4.py                # eine fertige Reihe wiederholen; Ergebnis in $CPE_RIG_WORK/results4.json

Argumente: `X:Y:WORT=WERT`, `X:Y` ist die Die-Koordinate des CPE, `WERT` ein Bitstring wie in `bitfile.txt` (MSB zuerst, z. B. `C_FUNCTION=001`,
`INIT_L10=0110`), `-` löscht das Wort (= 0). Wortnamen stehen in `libgm/src/TileBitDatabase.cpp` (`add_cpe`).
Nach den Messungen das Referenzdesign neu laden: `openFPGALoader -c gatemate_pgm ../uart_hello/bitfile.bit`.

## Methode

1. **Baseline:** `base/top.v` wird mit Yosys und nextpnr (`--seed 25`) gebaut. Der Bitstream ist deterministisch, die Platzierung ist immer dieselbe
   (3299 Zeilen `bitfile.txt`). Ändert man `base/top.v`, ändert sich die Platzierung, und die Tabelle unten muss neu aus `pnr.json` abgeleitet werden.
2. **Patch:** `rig.py` ändert Worte einzelner CPEs in `bitfile.txt` (auch in Tiles, die nextpnr nicht benutzt hat; diese werden neu angelegt).
   Routing (IM/SB-Bits) bleibt unverändert. Messbar ist daher nur, was über die schon verlegten Signale und die direkten Nachbar-Verbindungen
   (`COUTX -> CINX` nach rechts, `COUTY1/2 -> CINY1/2` nach oben) läuft.
3. **Lesen:** Der feste Leser (Addierer) liefert `Summe = A ^ B' ^ CI`, also `B' = s ^ A ^ CI`. `B'` ist der Wert, der auf `CINX` des Lesers ankommt,
   das ist `COUTX` des Testobjekts. Pro Messung gibt es `B'(B=0)` und `B'(B=1)`: `0` / `1` (konstant), `B` / `~B` (folgt B) oder `x` (die acht Zeilen
   widersprechen sich).

### Abbildung Die-Koordinate -> Bitstream

CPE `(x, y)` liegt in Tile `0 {(x-1)//2} {(y-1)//2}` und heißt dort `CPE{1 + (y gerade) + 2*(x gerade)}`. Geprüft an fünf CPEs des Baseline-Designs.

### Feste Positionen im Baseline-Design

| CPE | Position | Tile / Präfix | Rolle |
|---|---|---|---|
| Testobjekt | X146Y19 | `0 72 9` `CPE3` | Bridge; einzige dynamische Größe `IN7 = B` (`C_BR=1`, `C_SN=110`, `C_O1=01`, `C_CX_I=1`); `COUTX` speist den Leser |
| Leser (Addierer) | X147Y19 | `0 73 9` `CPE1` | `C_FUNCTION=001`; A über `PINY1`, B über `CINX`, CI über `CINY1` |
| Carry-Out | X147Y20 | `0 73 9` `CPE2` | `C_FUNCTION=101`, liest `CINY1` |
| Carry-In | X147Y18 | `0 73 8` `CPE2` | treibt `COUTY1 -> CINY1` des Lesers |
| West-Nachbar | X145Y19 | `0 72 9` `CPE1` | unbenutzt; als Konstantenquelle für `CINX` konfigurierbar (M14) |
| Süd-Nachbar | X146Y18 | `0 72 8` `CPE4` | unbenutzt; Konstantenquelle für `CINY1`/`CINY2` (M13, M15) |

### Konstantenquellen (Nachbarn)

Ein unbenutzter Nachbar wird per Patch zur Quelle: `OUT1 = COMBOUT1` (`C_O1=11`, `INIT_L20` = 0000/1111), `OUT2 = COMBOUT2` (`C_O2=11`, `INIT_L10`),
dann auf die Linie: `C_CX_I=1` (+ `C_SELX`, `C_SEL_C`) für `COUTX`; `C_CY1_I=1`, `C_SELY1=1` für `COUTY1`; `C_CY2_I=1`, `C_SELY2=1` für `COUTY2`
(nextpnr-Konfiguration der Routing-Pips). Rezepte stehen in `experiments/batch4.py`, `batch5.py`, `batch6.py`.

### Neue Reihe schreiben

Eine Reihe ist eine Schleife über Konfigurationen: `edits = {(x, y, 'WORT'): 'WERT' | None, ...}`, `line = run(name, edits)`, `bprime(line)`,
Ergebnis nach `WORK/resultsN.json`. Als Vorlage `experiments/batch2.py` (viele Kombinationen) oder `batch4.py` (Nachbar als Quelle). Eine Messung dauert
ca. 15 s; lange Reihen im Hintergrund starten und das Ende abwarten, nicht pollen.

## Fallstricke (gelernt)

- **Nicht angeschlossene `IN*` lesen sich als 1.** Gelesen aus `C_FUNCTION=3`/`C_HORIZ=1` (M11). Muster mit `D0`-Eingängen der LUTs sind damit nicht
  eindeutig; INITs so wählen, dass sie `D0` ignorieren, oder das Verhalten bewusst einplanen.
- **`C_RAM_I1/2`:** In der Hardware (nextpnr-Konfiguration ohne `C_RAM_I`) kommt `OUT1`/`OUT2` aus dem Ausgangsmux. `cpe.v` hat die Polarität des Schematics
  (1 = Ausgangsmux); `tb_coutx.v` setzt deshalb `C_RAM_I1 = C_RAM_I2 = 1`.
- **`PATH`:** `nextpnr-himbaechel` kommt aus `C:\Users\mio\source\nextpnr\build\Release` (steht vor `C:\oss-cad-suite\bin`). Der oss-cad-suite-Build
  kennt `--vopt lookahead=table` nicht. `PATH` nicht ändern.
- **Auslesen:** `rig.py` öffnet das Scope selbst (12 ms/div, Single-Shot, Trigger auf `UART0_TX`). Gibt `capture()` `None` zurück, hat das Testdesign nicht geladen
  oder das Scope nicht getriggert (`B'` = `?`).
- **Unbenutzte Tiles haben keine Worte.** Ein neuer Nachbar-CPE bekommt nur, was gepatcht wird; alles andere ist 0.
- **Messobjekt hängt am Leser:** Was der Leser nicht sieht (z. B. `POUTX`, `COUTY*`), braucht einen anderen Leser. Dessen Platzierung folgt aus `pnr.json`
  (`NEXTPNR_BEL`) der Baseline; die Abbildung oben macht daraus Tile und Wortpräfix.
- Beim Ändern der Baseline oder der Reihen immer zuerst `python rig.py base0` und eine bekannte Reihe (`experiments/batch4.py`, Vergleich mit `data/results4.json`)
  laufen lassen. So wurde die Kopie in `lab/` geprüft: Baseline identisch, `batch4` reproduziert (8 von 8).

## Regressionstest gegen `cpe.v`

    python make_tb_coutx.py > ../../schematics/cpe/sim/tb_coutx.v
    cd ../../schematics/cpe/sim && iverilog -g2012 -o coutx.vvp tb_coutx.v cpe.v && vvp coutx.vvp     # coutx test: all 142 hardware cases match

Neue Reihen: Ergebnisdatei nach `data/` kopieren und das Skript erweitern (`results4/5` zeigen, wie Nachbar-Konstanten als Parameter eingehen).

## `truth_rig/` (Methode B)

Wahrheitstabellen-Rig: Jeder interne Eingangspin des Testobjekts bekommt ein eigenes Signal (Bit eines Zählers, 50 % Tastverhältnis), `UART0_TX` ist der Referenztakt (Anfang einer vollständigen
Aufzählung aller 2^14 Kombinationen), `UART0_RX` der Messpin. Eine Aufnahme liefert die vollständige Funktion des Pins; Vergleich mit `cpe.v` über `expected()`.
Bauen, Kalibrieren (Pin- und Leserpolarität!), Messen: `truth_rig/README.md`. Abnahme und erste Befunde: `schematics/cpe/sim/hw_measurements.md`, M16 ... M18.
