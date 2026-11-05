# Lab-Umgebung (GateMate-Board + Rigol-Scope)

Alles hier ist so gebaut, dass Claude/Skripte Hardware-Ergebnisse selbst prüfen können.

## Hardware
| Teil | Details |
|---|---|
| FPGA | Cologne Chip GateMate CCGM1A1 (idcode 0x20000001), custom Board |
| Programmer | Cologne Chip "GateMate FPGA Programmer" (FT232H, 0403:6014), Kabel `-c gatemate_pgm` |
| Scope | Rigol MHO984, `192.168.2.165`, SCPI raw TCP **Port 5555** (kein VISA nötig) |
| Scope CH1 | `UART0_TX` (FPGA-Pin `IO_NA_A1`), **Probe 10x** (`:CHANx:PROB 10`), 1 V/div |
| Scope CH2 | `UART0_RX` (FPGA-Pin `IO_NA_B1`), **Probe 10x** |
| Takt | 12 MHz an `CLK12M` = `IO_SB_A8` (sdc: period 83.0) |

**Die Probes sind 10x. Den Probe-Faktor nie auf 1x setzen/annehmen** (das hat einmal ein Pegelproblem vorgetäuscht: 2.7 V erschienen als 0.28 V).

Pinbelegung (Referenz): `C:\Users\mio\source\synogate\gatery\tests\export\arch_colognechip_sdcard_sandbox\top.ccf`
(UART0, SD0, SPI-Flash, HyperRAM). Eigene Kopie für Tests: `uart_hello/pins.ccf`.

## Toolchain (Windows, in PATH via oss-cad-suite `C:\oss-cad-suite\bin`)
- `yosys` (`synth_gatemate -top top -luttree -nomx8 -json`), `nextpnr-himbaechel --device CCGM1A1`, `gmpack ... --reconfig`, `openFPGALoader`, `make` (SysGCC).
- Fertiger Flow: `cd lab/uart_hello && make prog` -> Synthese, PnR, Bitstream, Laden per JTAG (SRAM, wenige Sekunden).
  Erfolgsmeldung: `Wait for CFG_DONE DONE`. Nur laden: `openFPGALoader -c gatemate_pgm bitfile.bit`.
  Detect: `openFPGALoader -c gatemate_pgm --detect`; USB-Scan: `openFPGALoader --scan-usb`.
- SRAM-Konfiguration bleibt bis Power-Cycle oder nächstem Laden. Welches Design gerade läuft, merkt man sich selbst (zuletzt geladenes).
- Flash (persistent): `openFPGALoader --bulk-erase -c gatemate_pgm`, dann `-f --verify -c gatemate_pgm x.bit` (siehe Makefile im gatery-Beispiel).
- Gatery-VHDL->Verilog-Flow: Makefile im gatery-Beispielordner (nutzt `wsl sed`, ghdl).

## Scope steuern (`scope.py`, nur Python-Stdlib)
```python
from scope import *
s = Scope()                    # verbindet 192.168.2.165:5555
s.idn()
s.setup_uart(tscale=2e-3)      # CH1+CH2 DC, 10x, 1V/div, Edge-Trigger fallend 1.65V auf CH1
s.single(timeout=5)            # STOP, CLE, SING; True wenn getriggert
t, v = s.waveform("CHAN1")     # RAW, ganzer Speicher (1M Punkte), Volt
decode_uart(t, v, 115200)      # -> [(zeit, byte)]
s.meas("VAVG","CHAN1"); s.screenshot("shot.png")
```
CLI: `python capture_uart.py [baud] [s/div]` (Single-Shot, dekodiert TX und RX). Getestet mit 0.5/1/2 ms/div, jeweils 1M Punkte.

### Scope-Fallstricke (schon gelernt!)
1. **Daten immer per Single-Shot holen**: `s.single()` = `:STOP`, `:CLE`, `:SING`, dann kurz auf Armed (nicht `STOP`, max. 0,3 s) warten, dann `:TRIG:STAT?` pollen bis `STOP`; erst dann Waveform/Messwerte lesen. **Nie AUTO/RUN zum Erfassen**: bei langsamem Auslesen mischen sich Daten mehrerer Trigger-Events.
2. Direkt nach `:SING` liefert `:TRIG:STAT?` noch kurz `STOP` (Race) -> `single()` wartet darauf.
   **Speichertiefe fest setzen** (`:ACQ:MDEP 1000000`, macht `setup_uart()`): bei `Auto` ändert sich die Punktzahl mit dem Zeitmaßstab und der Waveform-Read liefert falsche/kurze Daten.
3. Im Trigger-Modus Normal/WAIT (ohne Trigger) frieren Anzeige und `:MEAS:ITEM?` ein -> veraltete Werte. `s.run_auto()` nur zum Live-Ansehen, nicht zum Erfassen.
4. Waveform: `:WAV:POIN` auf `:ACQ:MDEP?` setzen, sonst kommt nur ein 125k-Fragment (bei 1 GSa/s nur 125 us!). **Vorher `:WAV:STAR 1` / `:WAV:STOP n` zurücksetzen**: Reste vom vorigen Chunk-Read verkleinern sonst POIN (jeder 2. Read war leer/kurz). `waveform()` prüft die Punktzahl im Preamble. Umrechnung `(byte - yorigin - yreference) * yincrement` aus `:WAV:PRE?`; Chunks mit `:WAV:STAR/STOP`.
5. Screenshot: `:DISP:DATA? PNG` -> IEEE-Block (`#9...`); mit dem Read-Tool ansehbar.
6. Messwert `9.9E37` = ungültig. Eine TCP-Session reicht; nach Timeout neue `Scope()` öffnen.
7. Beim Schreiben von Dateien aus Python mit Sonderzeichen: `encoding="utf-8"` angeben (cp1252-Default auf Windows hat einmal README.md auf 0 Bytes gekürzt).

## Testdesigns
- `uart_hello/` - sendet `Hello GM#n\r\n` @115200 8N1 auf UART0_TX (Verilog, offener Flow), Pause ca. 50 ms. Idle-High am Scope ca. 2.7 V. Dekodierung verifiziert.
- `const_high/` - TX konstant 1/0 (zum Prüfen des Pin-Pegels).
- `cpe_rig/` - Harness für CPE-Validierung (Patch-Rig mit Baseline-Design, Messreihen und Rohdaten, `rig.py`, Anleitung in `cpe_rig/README.md`). Arbeitet in einem Ordner außerhalb von `lab/`.
