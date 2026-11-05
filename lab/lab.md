# lab.md – Anweisungen für Claude-Sessions im Labor

Ziel: Ergebnisse auf echter Hardware selbst prüfen (Design bauen -> laden -> am Scope messen/dekodieren).
Details/Hintergrund: `README.md` in diesem Ordner. Hier steht nur, **wie du vorgehst**.

## Aufbau (fest verdrahtet)
- Custom Board mit GateMate CCGM1A1, Programmer Cologne Chip (FTDI) via `openFPGALoader -c gatemate_pgm`.
- Scope Rigol MHO984 `192.168.2.165:5555` (raw SCPI, `lab/scope.py`).
- Scope CH1 = `UART0_TX` (FPGA `IO_NA_A1`), CH2 = `UART0_RX` (`IO_NA_B1`). **Probes sind 10x** – nie auf 1x stellen.
- Takt 12 MHz an `CLK12M` (`IO_SB_A8`). Pins für alles andere: `C:\Users\mio\source\synogate\gatery\tests\export\arch_colognechip_sdcard_sandbox\top.ccf`.
- Tools (yosys, nextpnr-himbaechel, gmpack, openFPGALoader) sind in PATH (`C:\oss-cad-suite\bin`). Shell: Git Bash; Python 3.13 ohne Zusatzpakete.

## `lab/` ist für Experimente schreibgeschützt
Experimente ändern den Ordner `lab/` **nicht**. Alles, was ein Experiment erzeugt, liegt in einem **Arbeitsordner außerhalb von `lab/`** (z. B. im Scratchpad der Session oder `$TEMP/lab_<name>`):
- Testdesigns, Build-Ausgaben (`synth.json`, `pnr.json`, `bitfile.*`, Logs), Skripte, Screenshots, Messdaten und Zwischenergebnisse.
- In `lab/` nichts anlegen, ändern oder löschen: keine neuen Ordner/Dateien, keine Änderungen an `scope.py`, `capture_uart.py`, `README.md`, `lab.md`, `uart_hello/`, `const_high/`, `cpe_rig/`.
- Python, das `scope` importiert, erzeugt sonst `lab/__pycache__`: `PYTHONDONTWRITEBYTECODE=1` setzen oder `sys.dont_write_bytecode = True` **vor** dem Import.
- **CPE-Validierung:** Dafür gibt es den fertigen Harness `lab/cpe_rig/` (Patch-Rig, Baseline-Design, Messreihen, Rohdaten, Anleitung in `cpe_rig/README.md`). Er schreibt nur in einen
  Arbeitsordner außerhalb von `lab/` (`CPE_RIG_WORK`, Standard `%TEMP%\cpe_rig_work`) und wird vor neuen CPE-Messungen als Erstes gelesen und benutzt. Neue Reihen schreibt man im Arbeitsordner
  (Vorlage: `cpe_rig/experiments/`); in den Harness kommt nur etwas auf ausdrücklichen Wunsch des Nutzers.
- Erkenntnisse aus Experimenten im Chat berichten. `README.md`/`lab.md` nur ändern, wenn der Nutzer es ausdrücklich verlangt (ebenso Änderungen an `scope.py` und den Referenzdesigns).

## Standard-Ablauf
1. Neues Testdesign im Arbeitsordner anlegen: `mkdir -p <arbeitsordner>` und `Makefile`, `pins.ccf`, `top.sdc` aus `lab/uart_hello` dorthin **kopieren** (`cp`), `top.v` im Arbeitsordner schreiben. `pins.ccf` enthält nur UART0 + CLK12M; weitere Pins aus der Referenz-`top.ccf` ergänzen (in der Kopie).
2. `cd <arbeitsordner> && make prog` (Synthese + PnR + gmpack + JTAG-Laden, SRAM). Erfolg = `Wait for CFG_DONE DONE`. Bei Timing-/PnR-Fehler Log lesen, nicht raten.
   Achtung: `cd` immer mit absolutem Pfad; das Arbeitsverzeichnis ändert sich zwischen Aufrufen. Nach dem Experiment kann man das Referenzdesign neu laden: `openFPGALoader -c gatemate_pgm /c/Users/mio/source/prjpeppercorn/lab/uart_hello/bitfile.bit` (nur lesen, ändert `lab/` nicht).
3. Messen mit `scope.py` (siehe unten). Ergebnis immer **dekodiert/gemessen** belegen, nicht annehmen.
4. Zum Gegenprüfen visuell: `s.screenshot(r"<arbeitsordner>\shot.png")` (Pfad im Arbeitsordner, nicht in `lab/`) und mit dem Read-Tool ansehen.

## Scope – Regeln (jede wurde durch einen Fehler gelernt)
- **Immer Single-Shot**: `s.single()` (= `:STOP`, `:CLE`, `:SING`, auf Trigger warten). Niemals AUTO/RUN zum Erfassen (gemischte Daten mehrerer Trigger-Events). `run_auto()` nur zum Live-Ansehen.
- **Speichertiefe fest** (`:ACQ:MDEP 1000000`) – `setup_uart()` macht das. Bei Auto ändert sich die Punktzahl mit dem Zeitmaßstab.
- Waveform: `waveform()` setzt STAR/STOP/POIN zurück und prüft die Punktzahl – nicht mit eigenen `:WAV:`-Befehlen umgehen.
- Probe-Faktor 10x, Trigger 1.65 V fallend auf CH1 (Startbit), Idle-High am Scope ≈ 2.7 V.
- Ohne Trigger ist die Wellenform leer; `single()` gibt dann `False` – das heißt „kein Signal“, kein Scope-Fehler.
- Dateien aus Python immer mit `encoding="utf-8"` schreiben (cp1252 hat einmal eine Datei auf 0 Bytes gekürzt). Besser: Write/Edit-Tool nutzen.
- Wird `scope.py` auf ausdrücklichen Wunsch des Nutzers geändert, danach mit `uart_hello` gegenprüfen (muss `Hello GM#n` liefern).

## Snippets
```python
import sys; sys.dont_write_bytecode = True        # sonst entsteht lab/__pycache__
sys.path.insert(0, r"C:\Users\mio\source\prjpeppercorn\lab")
from scope import *
s = Scope(); s.setup_uart(tscale=2e-3)        # 2 ms/div ≈ 24 ms Fenster, 1M Punkte
if s.single(5):
    t, v = s.waveform("CHAN1")                 # TX; "CHAN2" = RX
    print(bytes(b for _, b in decode_uart(t, v, 115200)))
```
- CLI: `PYTHONDONTWRITEBYTECODE=1 python lab/capture_uart.py [baud] [s_pro_div]` (dekodiert TX und RX; schreibt nichts nach `lab/`).
- Andere Baudraten/Formate: `decode_uart(t, v, baud, bits=8)` (8N1, LSB first, Idle high; keine Parität-Prüfung implementiert).
- Pegel/Frequenz: `s.meas("VAVG"|"VMAX"|"VMIN"|"FREQ", "CHAN1")` (nach `single()`/im Laufbetrieb; `9.9E37` = ungültig).
- Anderer Trigger/Signal-Typ: `setup_uart()` ist nur ein Preset – bei Bedarf `s.w(":TRIG:...")` direkt, Parameter `probe`, `mdepth`, `level`, `edge`, `src` sind einstellbar.

## Bekannter Zustand / Hinweise
- Nach dem Laden bleibt das Design im SRAM bis Power-Cycle oder nächstes Laden. Zuletzt geladen: `lab/uart_hello`. Für persistente Konfiguration Flash-Flow im Makefile des gatery-Beispiels (`--bulk-erase`, dann `-f --verify`).
- UART0_RX wird vom Board-Host/FTDI nicht getrieben; um RX zu testen, muss etwas extern senden (offen).
- Die Gatery-Beispiele nutzen ghdl -> yosys und `wsl sed`; für reine Verilog-Tests ist das nicht nötig.
- Wenn etwas „nicht funktioniert“: zuerst Probe-Faktor, Speichertiefe, Trigger-Zustand und Screenshot prüfen, bevor das Design verdächtigt wird.
- Neue Erkenntnisse im Chat berichten (siehe „`lab/` ist für Experimente schreibgeschützt“); `README.md` (Fallstricke) und diese Datei nur auf ausdrückliche Anfrage des Nutzers ergänzen.
