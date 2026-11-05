# Wahrheitstabellen-Rig (Methode B)

Eine Messung liefert die **vollständige Ausgangsfunktion** eines CPE-Pins über alle 2^14 Kombinationen seiner Eingänge. Aufbau:

- Ein Zähler (12 MHz) erzeugt 14 orthogonale Rechtecksignale `x[k]` (Bit `k` des Zählers, **50 % Tastverhältnis**, `f_k = 12 MHz / 2^(k+1)`, `k = 0 ... 13`),
  je durch ein eigenes Flop registriert. Jeder interne Eingangspin des Testobjekts bekommt ein anderes `x[k]`.
- **`UART0_TX` = Referenztakt:** Bit 14 des Zählers (366 Hz). Seine steigende Flanke ist der Anfang einer vollständigen Aufzählung aller 2^14 Zustände
  (Halbperiode = 2^14 Takte = 1,365 ms); das Scope triggert darauf (CH1, steigend), `t = 0` ist der Zustand `s = 0`.
- **`UART0_RX` = Messpin** (FPGA-Ausgang, Scope CH2): Ausgang des Lesers am Testobjekt.
- Aus der Aufnahme: `tick` = (fallende - steigende Flanke der Referenz) / 2^14 (= 83,333 ns), Ausgangsverzögerung aus der Phase der Ausgangsflanken, dann Pegel des Ausgangs spät in
  jedem Zustand `s`. Ergebnis `F[s]` (Zustand `s`: `x[k]` = Bit `k` von `s`). Eine Messung dauert mit Laden und Auslesen ca. 7 s.

Vergleich mit dem Modell: `expected()` rechnet dieselbe Tabelle mit `cpe.v` (`sim/expect.py`), `compare()` zählt die abweichenden Zustände.
Ein **Treffer ist 0 Abweichungen von 16384**. Welche Eingänge eine Funktion wirklich benutzt, welche Auswahl-Bedingungen (Muxe) gelten und welche Polarität der Weg hat,
folgt aus der Tabelle (Kofaktoren: für welche Belegungen der übrigen Eingänge ist `F = x_k` bzw. `~x_k`).

## Dateien

| Datei | Inhalt |
|---|---|
| `top.v`, `Makefile`, `pins.ccf`, `top.sdc` | das Design (Testobjekt `CC_MX8`, W/S/Reader `CC_L2T4` per `BEL` auf feste CPE-Hälften), `place_mx8.py` (`--pre-place`-Hook: bindet den MX8 und seine drei Dummy-Zellen an X146Y19, weil der Packer `BEL` bei MX8 verwirft) und der Build (nextpnr mit `--vopt no-cpe-cp`) |
| `tt_rig.py` | Bauen, Zuordnung aus `pnr.json`, Kalibrierung, Patchen, Laden, Aufnehmen, Extrahieren, Vergleichen; Kommandozeile und Bibliothek |

    cd /c/Users/mio/source/prjpeppercorn/lab/cpe_rig/truth_rig
    python tt_rig.py build                  # einmal; alles im Arbeitsordner CPE_RIG_WORK/truth (nicht in lab/)
    python tt_rig.py calibrate              # Polarität: Leser und IN1..IN8 (9 Messungen)
    python tt_rig.py run NAME 146:19:C_FUNCTION=001 146:19:C_HORIZ=1 ...     # DUT-Worte patchen und gegen cpe.v (COUTX) vergleichen

Als Bibliothek: `measure(name, dut_words)` (Wert `None` löscht ein Wort; Nachbar W ist als Quelle von `CINX = x[8]` vorkonfiguriert), `expected(dut_words)`, `bit(k)`, `compare(F, G)`.

## Positionen

| Zelle | Position | Eingänge |
|---|---|---|
| Testobjekt `dut` (`CC_MX8`) | X146Y19 | `IN1..IN8` = `x[0..7]`, garantiert ohne Tausch und ohne Inversion (nextpnr bricht sonst ab); `S0..S2` = `x[8..10]` auf CLK/EN/SR. Die Zelle wird per Patch zur CPE under test umgebaut (`C_CPE_*` des MX8 werden entfernt) |
| West-Nachbar `w_u` | X145Y19 | `x[8]`, `x[9]` (`CINX`, `PINX` des Testobjekts) |
| Süd-Nachbar `s_u` | X146Y18 | `x[10..13]` (`CINY1`, `CINY2`, `PINY1`, `PINY2`); je Nachbar nur zwei unabhängige Signale gleichzeitig |
| Leser `r_u` | X147Y19 | `C_I2 = 1`: `CINX` des Lesers = `COUTX` des Testobjekts, Ausgang -> `UART0_RX` |
| Dummy-Zellen | X145Y19, X146Y18, X147Y19 `LT_L`; X146Y20, X147Y20 beide Hälften | halten die Flops des Zählers aus den CPEs, die gepatcht werden |

## Wichtige Eigenschaften und Fallstricke

- **`--vopt no-cpe-cp` ist Pflicht.** Ohne die Option legt nextpnr gewöhnliche Eingänge über `CINX`/`PINY1` der Nachbarn und verfälscht die Messung.
- **Eingangspins können invertiert ankommen.** Nextpnr nutzt invertierende Routing-Pips und kompensiert das in seinen eigenen INIT-Worten (`bitstream.cc`, `update_cpe_lt`). Patcht man INIT-Worte,
  gilt die Kompensation nicht mehr. In diesem Bau: `IN1`, `IN4`, `IN6` direkt, `IN2`, `IN3`, `IN5`, `IN7`, `IN8` **invertiert**. `calibrate()` misst das (Identität über den 8:1-Mux), `expected()`
  wendet es an. **Nach jedem Neubau neu kalibrieren**; die Zuordnung `INx -> x[k]` kommt aus `pnr.json`.
- **Leser-Polarität** kann je Bau invertiert sein (ebenfalls in `calibrate()`).
- **Platzierung:** nextpnr setzt sonst die Zähler-Flops in die Nachbar-CPEs; die Dummy-Zellen verhindern das. Nach Änderungen an `top.v` mit `pnr.json` prüfen (`NEXTPNR_BEL`, nur `IN1..IN4` an den Zellen).
- **Zeitfenster:** `tscale = 0,25 ms/div` (+-4 ms um den Trigger), 1 M Punkte. Kurze Lesevorgänge des Scopes werden erkannt und wiederholt.
- Glitches an den Zustandsgrenzen (Eingänge mit verschiedenen Laufzeiten) werden durch das späte Abtasten (50-95 % eines Zustands) ausgeblendet. `unsure_states` zählt Zustände mit unklarem Pegel (soll 0 sein).
- Reine Kombinatorik: Funktionen, die von Registern abhängen (`C_O1`/`C_O2 = 00`), haben beim Laden einen undefinierten Anfang.

## Stand der Abnahme

Gemessen (siehe `sim/hw_measurements.md`, M16 ... M18): Identität über den 8:1-Mux (`IN1`) und `CINX`-Durchreichung (`C_FUNCTION=0`, `C_CX_I=0`) stimmen mit `cpe.v` in allen 16384 Zuständen. Offen:
Quellen für `CINY1/2`, `PINY1/2` (Süd-Nachbar), Leser für die Y-Linien (Relais X146Y20, Leser X147Y20) und die Auswertung zusammengesetzter Funktionen als Muxbaum (bisher nur Vergleich mit `cpe.v`).
