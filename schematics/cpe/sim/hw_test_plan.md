# Verifikationsplan für den CPE (Hardware gegen `cpe.v`)

Dieser Plan ist so geschrieben, dass ihn ein anderes Modell ohne den bisherigen Chatverlauf ausführen kann. Ziel: Jede Funktion, jedes Config-Bit und jeden Eingang
der CP-Linien (Carry/Propagate) des CPE auf dem echten GateMate messen, mit `cpe.v` vergleichen und das Modell nachführen. Bisherige Ergebnisse stehen in
`hw_measurements.md` (Messungen `M00` ... `M15`), das Modell ist `cpe.v`, das Schematic ist `../cpe.kicad_sch`.

## 0. Lies zuerst (in dieser Reihenfolge)

1. `/c/Users/mio/source/prjpeppercorn/lab/lab.md` und `lab/README.md`: Board, Scope, Regeln. **`lab/` bleibt unverändert**, außer `lab/cpe_rig/data/` (siehe Abschnitt 8).
2. `lab/cpe_rig/README.md`: Harness, Koordinaten-Abbildung, feste Positionen, Fallstricke.
3. `hw_measurements.md`: was schon gemessen ist, mit Rohdaten (nicht doppelt messen).
4. `cpe.v`: das Modell. Alle Kommentare `NOTE:` markieren Stellen, an denen Messung und Schematic abweichen.
5. `expect.py` (in diesem Ordner): liefert die Erwartung von `cpe.v` für eine Konfiguration (Abschnitt 4.2).
6. `lab/cpe_rig/truth_rig/README.md`: das **Wahrheitstabellen-Rig** (Methode B, Abschnitt 3.1). Es nutzt `UART0_TX` als Referenztakt und `UART0_RX` als Messpin.

## 1. Regeln für die Ausführung

- **Schematic nicht ändern.** Nachgeführt werden nur `cpe.v`, `tb_*.v`, `hw_measurements.md` und `lab/cpe_rig/data/`. Das Schematic und die gefalteten Sheets
  (`../cpe_f*.kicad_sch`) werden erst auf ausdrückliche Anweisung des Nutzers angepasst.
- **Nicht committen**, nichts löschen, was der Plan nicht ausdrücklich nennt. Nichts ins `PATH` exportieren (der nextpnr aus `C:\Users\mio\source\nextpnr\build\Release`
  muss vor `oss-cad-suite` bleiben).
- **Erst Rig prüfen, dann messen:** Vor jeder Sitzung `python rig.py base0` (erwartet `B'(B) = {0: 0, 1: 1}`) und eine bekannte Reihe nachmessen
  (`experiments/batch4.py`, Vergleich mit `data/results4.json`). Weicht das ab, ist der Aufbau kaputt, nicht das Modell.
- **Jede Messung ist ein Paar:** (Messwert aus Hardware, Erwartung aus `expect.py`). Ergebnis: `ok`, `abweichung` (mit Rohdaten) oder `unklar` (Aufbau erlaubt keine Aussage).
  Eine Abweichung erst als Modellfehler werten, wenn sie bei Wiederholung und mit einer zweiten, unabhängigen Konfiguration bestätigt ist.
- **Nach jeder Sitzung Referenzdesign laden:** `openFPGALoader -c gatemate_pgm /c/Users/mio/source/prjpeppercorn/lab/uart_hello/bitfile.bit`.
- Lange Reihen im Hintergrund starten (eine Messung ca. 15 s); nicht pollen, Ende abwarten. Immer **absolute Pfade** (`cd` setzt sich nicht fort).
- **Methode B:** `UART0_TX` führt den Referenztakt, `UART0_RX` (`IO_NA_B1`) ist ein **Ausgang des FPGA** (Scope CH2); nichts extern darauf treiben. Die Probes sind 10x (`lab/lab.md`).
- Dokumentation gehört in `hw_measurements.md` (neue Einträge `M20` ff., Rohdaten, Auswertung, Abweichung vom Modell). Fragen an den Nutzer nur, wenn Aufbau oder Freigaben fehlen.

## 2. Ausgangslage

### 2.1 Als unverdächtig angenommen (nicht einzeln prüfen)

Was nextpnr implementiert und benutzt, funktioniert so, wie nextpnr es erwartet: LUT-Baum (`INIT_L00` ... `L20` als Funktionen von `IN1..IN8`), `OUT1`/`OUT2`/`MUXOUT`
(8:1-Mux mit `C_BR`, `C_SN`), `COMBOUT1/2` (Adder-Summen), Register und Latches im üblichen Gebrauch, die von nextpnr gesetzten Routing-Pips für `COUTX/Y1/Y2`,
`POUTX/Y1/Y2` (`C_CX_I=1`, `C_SELX`, `C_SEL_C`, `C_CY1_I=1`, `C_SELY1`, `C_PX_I=1`, ...), `C_I1..C_I4`, die Modi `C_FUNCTION` = 1 (ADDF), 2 (ADDF2), 3 (MULT), 4 (MX4),
5 (EN_CIN), 7 (ADDCIN). Diese Stellen dienen als Messmittel; ihre **internen Details** (Polarität, Zusammenspiel) sind aber nur dort belegt, wo nextpnr sie benutzt.

### 2.2 Gemessen (Kurzfassung, Details in `hw_measurements.md`)

| ID | Aussage |
|---|---|
| M00-M04 | Addierer `C_FUNCTION=1`, `C_HORIZ=0`: `COUTY1 = (~C_CY1_I & (L10 ^ L11)) ? CINY1 : (L00 | L01)`. `C_HORIZ=1` gemessen (`CINY1 | (A&B)`), nicht im Modell |
| M10, M11 | `COUTX`: `chain = ~C_CX_I & (~(C_ADDF & C_HORIZ) | P)`, `alt = C_MULT | C_CX_I`, `P = L10^L11` (F=1,6) bzw. `L10&L11` (F=2,3); `G = L00|L01` (F=1,6), `G = L10 ? L02 : (L00|L01)` (F=2) |
| M12 | `cx_route` für `C_SEL_C`,`C_SELX` = 00: `OUT1`, 01: `OUT2`, 10: `COMP_OUT` **invertiert**, 11: `C_Y12 ? CINY2 : CINY1` |
| M13-M15 | `CINY1`/`CINY2` und `CINX` kommen unverändert in `COUTX` an; Kanäle Y1/Y2 nicht vertauscht |
| Nebenbefunde | Nicht angeschlossene `IN*` lesen sich als 1 (an `IN1` belegt). `C_RAM_I1/2` haben in der Hardware die umgekehrte Polarität wie in `cpe.v` (`expect.py` gleicht das aus) |

`cpe.v` ist für `COUTX` und `COUTY1` (Addierer, `C_HORIZ=0`) nachgeführt; `tb_coutx.v` (142 Fälle) und `tb_adder.v` (12 Fälle) bestehen.

### 2.3 Bekannt offen oder fragwürdig im Modell

- `COUTY1` mit `C_HORIZ=1` (M04 nicht erklärt).
- Alle Aussagen über `COUTY2`, `POUTX`, `POUTY1`, `POUTY2`, `CPOUT1/2` stammen noch aus dem Schematic. `C_CY2_I`, `C_PY1_I`, `C_PY2_I`, `C_PX_I` sind dort
  mit der Polarität „durchreichen bei 1“ gezeichnet, `die.py` und nextpnr haben „durchreichen bei 0“ (bei `COUTY1` hat sich das als richtig erwiesen).
- `COMP_OUT`-Inversion: nur auf `COUTX` gemessen. Ob sie im Komparator, in `INIT_L30` oder auf den Linien sitzt, ist offen.
- `G` für `C_FUNCTION=2` mit `L10=1` (dort ist `L02` 0): `L02`-Zweig nicht getrennt von `L00|L01` gemessen.
- Multiplikator (`MULTO1`, `MULTO2`, `COY2_S`, `COY2_a`): nur die Abhängigkeit von `L10`, `L11`, `CINX` (carry_in) ist bestätigt, nicht die von `IN5`, `IN8`, `PINY2`, `CINY1`, `CINY2`.
- Nicht überprüft: `C_2D_IN`, `C_C_P`, `C_COMP`, `C_COMP_I`, `C_SEL_P`, `C_CLKSEL`/`C_ENSEL`-Details, MX4-Maske, Latch-Setz-/Rücksetzlogik (siehe Abdeckungsmatrix, Abschnitt 7).

## 3. Aufbau und Grenzen

Das Patch-Rig ändert Config-Worte einzelner CPEs im fertigen Bitstream; das Routing bleibt unverändert. Es gilt (Details in `lab/cpe_rig/README.md`):

- CPE `(x,y)` -> Tile `0 {(x-1)//2} {(y-1)//2}`, Wortpräfix `CPE{1 + (y gerade) + 2*(x gerade)}`.
- **Testobjekt (DUT):** X146Y19 (`0 72 9` `CPE3`). Einzige dynamische Größe: `IN7 = B` (Wechselsignal des Testdesigns). Alle anderen `IN*` sind nicht angeschlossen (lesen 1).
- **West-Nachbar W** X145Y19 (`0 72 9` `CPE1`) speist `CINX` (`COUTX`) und `PINX` (`POUTX`) des DUT. **Süd-Nachbar S** X146Y18 (`0 72 8` `CPE4`) speist `CINY1`, `CINY2`
  (`COUTY1/2`) und `PINY1`, `PINY2` (`POUTY1/2`). Beide sind unbenutzt und werden per Patch zu Konstantenquellen (Rezepte unten).
- **Leser A** (Addierer X147Y19, `0 73 9` `CPE1`): sieht `COUTX` des DUT auf `CINX`. Messgröße `B' = s ^ A ^ CI`.
- **Leser C** (Carry-Out-CPE X147Y20, `0 73 9` `CPE2`, `C_FUNCTION=101`): sein `OUT1` landet im Testdesign als Bit `c` der UART-Zeile. Heute liest er `CINY1` (Carry des Addierers). Für Y-Linien
  wird er auf `CINX` umgestellt und über das **Relais** X146Y20 (`0 72 9` `CPE4`) gespeist (4.3, nicht erprobt).
- Eine Messung = ein Bitstream = ca. 15 s. Dynamisch ist nur B; für alles andere werden Konstanten per Konfiguration gesetzt (Neu-Bitstream pro Wert).

**Grenzen:** `IN1..IN6`, `IN8` des DUT sind nicht steuerbar (lesen 1). Damit sind `IN5` und `IN8` im Multiplikator (`pp_a0_b1 = IN5 & PINY2`, `pp_am1_b1 = IN8 & PINY2`) nur im Fall 1 prüfbar.
Methode B (Abschnitt 3.1) löst das: dort trägt jeder Eingang ein eigenes Signal.

### 3.1 Methode B: Wahrheitstabellen-Rig (Referenztakt auf UART0_TX, Messpin UART0_RX)

Methode A (oben) macht pro Bitstream nur B dynamisch. Methode B gibt **jedem internen Eingangspin** des Testobjekts ein eigenes Signal: 14 orthogonale Rechtecke mit **50 % Tastverhältnis** (Bit `k` eines Zählers,
`f_k = 12 MHz / 2^(k+1)`, je ein eigenes Flop). `UART0_TX` führt den **Referenztakt** (Bit 14 des Zählers), `UART0_RX` ist der **Messpin** (FPGA-Ausgang, Scope CH2). Weil die Eingänge die Bits eines Zählers sind,
durchläuft jede Halbperiode des Referenztakts **alle 2^14 Eingangskombinationen** genau einmal. Eine Aufnahme liefert damit die **vollständige Funktion** des Pins; die Logikfunktion und alle Muxe lassen sich eindeutig bestimmen,
mit einer Messung je Konfiguration (ca. 7 s).

**Fertig und abgenommen** (M16-M18 in `hw_measurements.md`): `lab/cpe_rig/truth_rig/` mit `top.v`, `Makefile` (nextpnr `--vopt no-cpe-cp`), `tt_rig.py` und `README.md`. Lies dessen README vollständig; die Eckpunkte:

- Aufbau: Testobjekt X146Y19 (`IN1..IN8` = `x[0..7]`), West-Nachbar X145Y19 (`CINX`, `PINX` = `x[8]`, `x[9]`), Süd-Nachbar X146Y18 (`CINY1/2`, `PINY1/2` = `x[10..13]`), Leser X147Y19. Platzierung per `BEL`-Attribut;
  Dummy-Zellen halten die Zähler-Flops aus den gepatchten CPEs.
- Auswertung: Scope triggert auf die steigende Flanke von CH1 (Referenz); `tick` aus der Referenz, Pegel von CH2 spät in jedem Zustand abtasten. Ergebnis `F[s]`, `s` = Zählerstand, `x[k]` = Bit `k` von `s`.
- Vergleich: `expected()` (aus `cpe.v` via `sim/expect.py`) gegen `F`; **0 Abweichungen von 16384** ist ein Treffer. Mit `compare()` und Kofaktoren lassen sich Abweichungen auf Eingänge und Bedingungen eingrenzen.
- **Pflicht nach jedem Neubau:** `python tt_rig.py calibrate`. Nextpnr routet Eingänge teils **invertiert** (hier `IN2`, `IN3`, `IN5`, `IN7`, `IN8`); gepatchte INIT-Worte sehen das Signal invertiert. Der Leser kann je Bau invertiert sein.
- Je Nachbar sind nur **zwei unabhängige Signale** gleichzeitig möglich (`OUT1`, `OUT2`); die vier Linien `CINY1/2`, `PINY1/2` aus dem Süd-Nachbarn teilen sich zwei Signale. Wer alle vier unabhängig braucht, nimmt einen zweiten
  Quell-CPE (X145Y18) und reicht dessen `COUTX` über den Süd-Nachbarn weiter (Idee, nicht erprobt).
- Y-Linien (`COUTY1/2`, `POUTY1/2`) und `POUTX` brauchen weitere Leser (Relais X146Y20, Leser X147Y20 bzw. `PINX` am Leser X147Y19; Rezepte in 4.3, nicht erprobt). Dafür sind die Dummy-Zellen bereits platziert.

**Zuerst durchführen (Abnahme in deiner Umgebung, Phase 0, V0.6):** `build`, `calibrate`, dann `run` mit (a) `C_BR=1`, `C_O1=01`, `C_SN=k`, `C_CX_I=1` (Identität, `k = 0..7`, soll 0 Abweichungen), (b) `C_FUNCTION=0`, `C_CX_I` gelöscht
(`CINX`-Durchreichung, 0 Abweichungen), (c) die Wahrheitstabelle `C_FUNCTION=001`, `C_HORIZ=1`, `C_CX_I` gelöscht, `INIT_L00..L03 = 1100`, `INIT_L10 = INIT_L11 = 0110` (**erwartet 5120 Abweichungen**: das ist der offene Widerspruch aus M18,
kein Fehler des Aufbaus).

## 4. Werkzeuge

### 4.1 Patch-Rig

    cd /c/Users/mio/source/prjpeppercorn/lab/cpe_rig
    python rig.py setup                      # Baseline im Arbeitsordner bauen (einmal)
    python rig.py NAME X:Y:WORT=WERT ...     # patchen, packen, laden, lesen ('-' löscht ein Wort)

Reihen: wie `experiments/batch2.py` (Produkt über Parameter, Ergebnis `WORK/resultsN.json`, `WORK` = `%TEMP%\cpe_rig_work`). `bprime()` dekodiert Leser A.

### 4.2 Erwartung aus dem Modell (`expect.py`)

    cd /c/Users/mio/source/prjpeppercorn/schematics/cpe/sim
    python expect.py C_FUNCTION=011 C_HORIZ=1 INIT_L10=1111 INIT_L03=1010 INIT_L11=1100 C_SN=000 -- IN7=0,1 CINX=0,1

Worte genauso wie beim Patchen (Bitstrings oder Zahlen). Nicht genannte Worte sind 0, nicht genannte `IN1..IN8` sind 1 (Hardware), `CINX/Y`, `PINX/Y`, `RAM_I` sind 0.
Ausgaben: `OUT1 OUT2 RAM_O1 RAM_O2 COUTX COUTY1 COUTY2 POUTX POUTY1 POUTY2`. Als Bibliothek: `expect(words, rows)`. Geprüft gegen M14.
Hinweis: `C_RAM_I1/2` werden in der Hardware-Polarität übergeben (Wort fehlt = Ausgangsmux).

### 4.3 Leser-Rezepte (zu validieren in Phase 0)

**Konstantenquellen**

| Nachbar | Wirkung | Wörter |
|---|---|---|
| W X145Y19 | `CINX` = v1 | `C_CX_I=1`, `C_O1=11`, `INIT_L20` = 1111 (v1=1) oder 0000 |
| W X145Y19 | zusätzlich `PINX` = v2 | `C_PX_I=1`, `C_SEL_P=0`, `C_SELX=0` (dann `px_route = OUT2`), `C_O2=11`, `INIT_L10` = v2 |
| S X146Y18 | `CINY1` = v1, `CINY2` = v2 | `C_CY1_I=1`, `C_SELY1=1`, `C_CY2_I=1`, `C_SELY2=1`, `C_O1=11`, `C_O2=11`, `INIT_L20` = v1, `INIT_L10` = v2 (M13, M15) |
| S X146Y18 | `PINY1`, `PINY2` | `C_PY1_I=1`, `C_PY2_I=1`, `C_SEL_P=0`: `PINY1 = SELY1 ? OUT2 : OUT1`, `PINY2 = SELY2 ? OUT1 : OUT2` (**nach dem Modell, ungemessen**, erst in Phase 0 bestätigen) |

**Leser A, `PINX` statt `CINX`:** auf X147Y19 `INIT_L01=0000`, `C_I4=1`, `INIT_L03=1100`, `INIT_L11=1100` (L10, L20 bleiben `0110`): dann `s = A ^ PINX ^ CI`, also `B' = PINX`.

**Y-Linien lesen (Relais + Leser C):**

- Relais X146Y20 (`0 72 9` `CPE4`): `C_CX_I=1`, `C_SEL_C=1`, `C_SELX=1`, `C_Y12=0` (reicht `CINY1` = `COUTY1` des DUT durch) bzw. `C_Y12=1` (`CINY2`). Für `POUTY1/2`: `C_PX_I=1`, `C_SEL_P=1`,
  `C_SELX=1`, `C_Y12=0/1` (`PINY1/2` -> `POUTX` des Relais, gemessen ist bisher nur der `COUTX`-Fall).
- Leser C X147Y20 (`0 73 9` `CPE2`): für `CINX`: `C_HORIZ=1` zu den vorhandenen Worten (`C_FUNCTION=101`); für `PINX`: `C_FUNCTION` löschen, `C_I4=1`, `INIT_L03=1100`.
  Das Ergebnis steht als Bit `c` in der UART-Zeile: `c(B)` für B = 0/1.
- Auswertung: `c` aus den acht Zeilen `i:cs`, `c(B) = c` der Zeilen mit `B = (i>>1)&1`; widersprechen sich die Zeilen, ist das Ergebnis `x`.
- Das Relais braucht für die Messung des **DUT** konstante Gegenstücke: sein eigener `CINY1/CINY2`-Eingang ist der DUT-Ausgang, alles andere (`IN*`) ist ohne Einfluss.

### 4.4 Auswertungscodes

Pro Messung wird `B'(B=0)`, `B'(B=1)` (bzw. `c(B)`) als `0`, `1`, `B`, `~B` oder `x` notiert. `?` = keine UART-Zeile (Design nicht geladen oder Scope nicht getriggert, wiederholen).

## 5. Methode je Test

1. **Aufbau wählen:** DUT-Wörter (Ausgang/Linie, die geprüft wird), Nachbarn als Konstantenquellen, Leser.
2. **Variationen:** Produkt über die genannten Wörter und Konstanten, die `L`-Werte so wählen, dass die zu prüfende Größe (`P`, `G`, `OUT*`, `COMP_OUT`, `CIN*`, `PIN*`) im Ergebnis **unterscheidbar** ist
   (Konstanten verschieden; die geprüfte Größe als B-abhängige Größe, z. B. `L11 = B` über `INIT_L03=1010`, `INIT_L11=1100`).
3. **Erwartung:** `expect.py` mit denselben Wörtern und `IN7=0,1`; Konstanten der Nachbarn als `CINX`, `CINY1`, ... eintragen.
4. **Vergleich:** Messwert gegen Erwartung; Abweichungen mit Rohdaten notieren.
5. **Nachführung:** Bei bestätigter Abweichung `cpe.v` (und `NOTE`-Kommentar) ändern, Fälle in `lab/cpe_rig/data/` und einen Testbench-Generator aufnehmen
   (`make_tb_coutx.py` als Vorlage), `hw_measurements.md` ergänzen.

## 6. Testkatalog

**Methode je Test:** A = Patch-Rig mit UART-Zeile (erprobt, ein dynamisches Signal B, Konstanten per Config); B = Wahrheitstabellen-Rig (Abschnitt 3.1, ein orthogonales Signal je Eingang, Pin `UART0_RX`, eine Messung je Konfiguration).
Wo mehrere Eingänge gleichzeitig unterscheidbar sein müssen, oder `IN1..IN6`, `IN8` gebraucht werden, ist B zu bevorzugen: X3, X4, X5, X6, PX.1, PX.3 - PX.5, PY1.1, CY2.1, CY2.2, PY2.1, CP.1, F.2, F.4.
A genügt für V0.x, X1, X2, Y1.x (mit dynamischem B und Konstanten), CP.2, F.1, F.3, F.5 und alles, was nur einen Eingang variiert. Jeden mit A gemessenen Fall, der mit B wiederholbar ist, einmal mit B gegenprüfen, sobald V0.6 bestanden ist. **Besonders wichtig:** der Generate-Term `G` (M18), er ist im Modell unsicher.

Priorität: P1 hoch ... P3 niedrig. Läufe sind Schätzungen. Wo nichts anderes steht: DUT-Basis `C_BR=1`, `C_SN=110` (`IN7`), `C_O1=01` (`OUT1 = B`), `C_CX_I=1`, `C_SELX=0`, `C_SEL_C=0`.

### Phase 0: Aufbau validieren (vor allem anderen)

| ID | Test | Erwartung / Kriterium | Läufe |
|---|---|---|---|
| V0.1 | Baseline und `batch4` wiederholen | wie `data/results4.json` | 9 |
| V0.2 | Leser A liest `PINX` (Abschnitt 4.3), W: `POUTX` = v2 mit `C_PX_I=1`, `C_SEL_P=0`, `C_SELX=0`, `C_O2=11`, `INIT_L10` = v2; `COUTX` von W = v1 (verschieden) | `B' = v2` bei `PINX`-Lesen, `B' = v1` bei `CINX`-Lesen. Trennt die beiden Linien | 8 |
| V0.3 | Relais + Leser C: DUT-`COUTY1` mit `C_CY1_I=1`, `C_SELY1=1`, `C_SEL_C=0`, `C_O1=01` (`OUT1 = B`); Relais `C_Y12=0` | `c(B)` folgt B; mit `C_O1`-Konstante folgt `c` der Konstante | 6 |
| V0.4 | Wie V0.3 für `COUTY2` (`C_CY2_I=1`, `C_SELY2=0` = `OUT1`) und `C_Y12=1` | `c(B)` folgt B | 4 |
| V0.5 | `POUTY1/2` als Quelle in S prüfen: S mit `C_PY1_I=1`, `C_PY2_I=1`, `C_SEL_P=0`, verschiedenen `C_SELY1/2` und Konstanten v1 (`OUT1`), v2 (`OUT2`). DUT reicht `pin_y12` nach `POUTX` durch (`C_PX_I=1`, `C_SEL_P=1`, `C_SELX=1`, `C_Y12=0/1`), Leser A liest `PINX` (V0.2) | `PINY1 = SELY1 ? v2 : v1`, `PINY2 = SELY2 ? v1 : v2` (Tabelle in 4.3) bestätigt oder korrigiert | 16 |
| V0.6 | Wahrheitstabellen-Rig abnehmen (Abschnitt 3.1): `build`, `calibrate`, Identität `k = 0..7`, `CINX`-Durchreichung, Wahrheitstabelle (c) | (a), (b) 0 Abweichungen; (c) 5120 Abweichungen (M18) | 14 |
| V0.7 | Leser-Variante Y des Wahrheitstabellen-Rigs (Relais X146Y20, Leser X147Y20): DUT `COUTY1` (`OUT1` = Mux-Ausgang) wird auf RX sichtbar | Tabelle = `x[k]` bzw. `~x[k]` der gewählten Eingänge | 8 |

### Phase 1 (P1): `COUTX` abschließen

| ID | Test | Läufe |
|---|---|---|
| X1 | `G` bei `C_FUNCTION=2`: `L02=1111` mit `L10=1`, `L00` = 0/1, `C_HORIZ=1`, `C_CX_I=0`, `L11` über `IN7` (vgl. M11) | 16 |
| X2 | `G` bei `C_FUNCTION=1/6` mit `L01`, `L02`, `L03` einzeln 1: bestätigt `G = L00 | L01` ohne `L02` | 12 |
| X3 | `C_Y12` und `C_SELX`/`C_SEL_C` mit allen vier `cx_route`-Eingängen **gleichzeitig verschieden** (OUT1=B, OUT2=Konstante, COMP_OUT=Konstante, CIN=Konstante), jeder Eingang einzeln unterscheidbar | 16 |
| X4 | `COMP_OUT`-Inversion: `INIT_L30` alle 16 Werte, `comb1/comb2` über `L`-Wörter B-abhängig: lokalisieren, ob `~comp_out` oder invertierte `INIT_L30` (gegen `POUTX`, Phase 4) | 20 |
| X5 | `MULTO2` (`C_FUNCTION=011`): Abhängigkeit von `CINY1`, `CINY2` (S), `L10`, `L11`, `C_HORIZ` (carry_in = `CINX` bzw. `CINY1`) | 32 |
| X6 | `C_FUNCTION=4`, `5`, `7` mit nichttrivialen `L`-Werten (bisher nur 0-LUTs): `chain=1` wie `C_ADDF=0` | 12 |

### Phase 2 (P1): `COUTY1` (Leser C über Relais)

| ID | Test | Erwartung (aus `expect.py`) | Läufe |
|---|---|---|---|
| Y1.1 | `C_CY1_I=0`, `C_FUNCTION=0`, `C_HORIZ=0`: `COUTY1 = CINY1`? | `CINY1` aus S (v1 = 0/1) | 2 |
| Y1.2 | `C_CY1_I=1`, route: `C_SEL_C`,`C_SELY1` = 00 (`OUT2`), 01 (`OUT1`), 10 (`COMP_OUT`, Vorzeichen prüfen!), 11 (`CINX`) mit verschiedenen Konstanten | 4 Auswahlen, je 2 Konstantenpaare | 8 |
| Y1.3 | `C_FUNCTION` in {0,1,2,3,6,7} x `C_HORIZ` x `C_CY1_I` x `L10` x `L00` (wie M11, `L11 = B`) | `cy1_through`, `cy1_adder`, `P`, `G` aus `cpe.v` | 96 |
| Y1.4 | `C_HORIZ=1` mit Adder (M04): mit `CINX` aus W und `CINY1` aus S **beide unabhängig** variieren; Formel für `COUTY1` bei `C_HORIZ=1` bestimmen | Abweichung von `cpe.v` erwartet | 24 |
| Y1.5 | `G` bei `C_FUNCTION=2` (L10-Select) und `P` bei `C_FUNCTION=2,3` für `COUTY1` | `cpe.v` | 24 |

### Phase 3 (P1): `POUTX` (Leser A, `PINX`; nach V0.2)

| ID | Test | Läufe |
|---|---|---|
| PX.1 | `C_PX_I=1` (route), `{C_SEL_P, C_SELX}` = 00 (`OUT2`), 01 (`OUT1`), 10 (`COMP_OUT`), 11 (`pin_y12`, `C_Y12=0/1` = `PINY1/PINY2`): jeder Eingang einzeln unterscheidbar | 20 |
| PX.2 | `C_PX_I=0` ohne Komparator: Durchreichen von `PINX` (Polarität!) | 4 |
| PX.3 | `C_COMP`, `C_COMP_I`, `C_HORIZ`, `INIT_L30`: `poutx_chain = (comp_out | (C_COMP & C_HORIZ)) & ~C_PX_I`, `alt = C_MULT | C_PX_I`; D0 `C_COMP_I`, D3 `MULTO1` | 64 |
| PX.4 | `COMP_OUT` bei `C_FUNCTION` = 0..7 (`comb1/comb2` von der Funktion abhängig), Inversion lokalisieren (mit X4) | 32 |
| PX.5 | `MULTO1` (`C_FUNCTION=011`): `L11`, `CINY1` (carry_in), `CINY2`, `PINY2`, `IN8` | 24 |

### Phase 4 (P2): `POUTY1` und `COUTY2`/`POUTY2`

| ID | Test | Läufe |
|---|---|---|
| PY1.1 | `POUTY1`: Polarität von `C_PY1_I` (Schematic: durchreichen bei 1, `die.py`: bei 0), `py1_through`/`py1_compare`, `{C_SEL_P,C_SELY1}`-Eingänge (`OUT1`, `OUT2`, `COMP_OUT`, `PINX`) | 40 |
| CY2.1 | `COUTY2`: `C_CY2_I`-Polarität; `cy2_through = (coy2_s | C_MULT) & C_CY2_I` gegen Messung; Route `{C_SEL_C,C_SELY2}` | 48 |
| CY2.2 | `COY2_S`, `COY2_a` bei `C_FUNCTION=3` (Multiplikator-Summen): nur mit steuerbaren `IN5`, `IN8`, `PINY2` vollständig (Methode B) | 48 |
| PY2.1 | `POUTY2`: `py2_through = C_PY2_I | C_MULT`; Route `{C_SEL_P,C_SELY2}` | 32 |

### Phase 5 (P2): `CPOUT1/2`

`C_O1` / `C_O2` = 10 nehmen `cpout1`/`cpout2`, `C_C_P` vertauscht Carry und Propagate, `C_HORIZ | C_MULT` wählt X- oder Y1-Achse. Aufbau: `OUT1` über `C_CY2_I=1`, `C_SELY2=0` (`COUTY2 = OUT1`) auf
Leser C lesen (Relais `C_Y12=1`), DUT `COUTY1` auf `CINY1` pass-through oder Route, damit **keine Rückkopplung** `OUT1 -> COUTX -> OUT1` entsteht.

| ID | Test | Läufe |
|---|---|---|
| CP.1 | `C_C_P` x `C_HORIZ` x `C_MULT` (`C_FUNCTION=011`) x Quellen (`COUTY1`, `POUTY1`, `COUTX`, `POUTX` mit verschiedenen Konstanten) | 32 |
| CP.2 | Zuordnung `CPE_LT_U`/`CPE_LT_L` zu `CPOUT1/2`: aus nextpnr-Konfiguration `CPOUT` an `CPE_LT_L` -> `CPOUT1_int`? (`die.py:3009/3061`), mit einem nextpnr-Design und seinem Bitstream | 4 |

### Phase 6 (P2): Funktionsmodi und Komparator

| ID | Test | Läufe |
|---|---|---|
| F.1 | `C_FUNCTION=2` (ADDF2): 2-Bit-Addierer mit `CC_ADDF` x2 (nextpnr verschmilzt zu einem CPE), alle 32 Kombinationen von {CI, A[1:0], B[1:0]}, Summe und `COUTY1` gegen `cpe.v` (neues Basisdesign `base_addf2`) | 1 + Patch-Varianten (`L02`, `L03`, `L10`, `L11`) 12 |
| F.2 | `C_FUNCTION=3` (MULT): nextpnr-Multiplikator (`CC_MULT`) als Basisdesign, Bitstream-Dekodierung der CPE-Konfiguration, Auswertung gegen `cpe.v` | 4-8 |
| F.3 | `C_FUNCTION=5` (EN_CIN): `l03 = l03_lut | (C_EN_CIN & carry_in)` mit `C_HORIZ=0/1` und `L03` | 8 |
| F.4 | `C_FUNCTION=6` (CONCAT) und `7` (ADDCIN): Summenausgang `COMB1OUT` / `COMB2OUT` über `OUT1`/`OUT2` (`C_O1=11`, `C_O2=11`) lesen | 16 |
| F.5 | `C_FUNCTION=4` (MX4) mit Maske: `INIT_L10`/`L11` als Invertier-/Selectbits | 16 |

### Phase 7 (P3): Rest

| ID | Test | Läufe |
|---|---|---|
| R.1 | 8:1-Mux mit Select-Addierer (`C_BR=0`, `C_SN`, `C_2D_IN`, LUT1-Terme `C_CPE_CLK/EN/RES`, `C_CLKSEL`/`C_ENSEL` mit `CINY1`/`PINY1` im Mux, `CINY2`/`PINY2` im Register) | 40 |
| R.2 | Register und Latches: `C_L_D`, `C_EN_SR`, Set-/Reset-Kreuzung, `C_2D_IN` (invertiertes `MUXOUT` in Flop 2) | 24 |
| R.3 | `C_RAM_I1/2`, `C_RAM_O1/2` (Polarität gegen `cpe.v`; RAM-Pfad braucht `RAM_I`/`RAM_O`-Quelle) | 8 |
| R.4 | `C_I3`, `C_I4` (`PINY1`/`PINX` als LUT-Eingänge; `C_I1`, `C_I2` sind durch den Leser belegt) | 8 |

## 7. Abdeckungsmatrix (Config-Worte)

Status: `gemessen` (ID), `Quelle` (als Messmittel von nextpnr benutzt, Details offen), `offen`.

| Wort | Status | Tests |
|---|---|---|
| `INIT_L00`..`L03`, `L10`, `L11`, `L20` | gemessen (M02, M11, M14) | X1, X2, F.* |
| `INIT_L30` | gemessen auf `COUTX` (M12) | X4, PX.3, PX.4 |
| `C_I1`, `C_I2` | Quelle (Leser A) | - |
| `C_I3`, `C_I4` | offen | V0.2 (`C_I4`), R.4 |
| `C_FUNCTION` | `COUTX` 0..7 gemessen; `COUTY1` nur 1 | Y1.3, F.1-F.5 |
| `C_HORIZ` | `COUTX` gemessen, `COUTY1` offen (M04) | Y1.4, PX.3, CP.1 |
| `C_CX_I`, `C_SEL_C`, `C_SELX`, `C_Y12` | gemessen auf `COUTX` | X3, PX.1 (gemeinsame Bits) |
| `C_CY1_I` | gemessen mit Adder (M02/M03); Route offen | Y1.1, Y1.2 |
| `C_SELY1`, `C_SELY2`, `C_CY2_I` | Quelle (S), Logik offen | Y1.2, CY2.1 |
| `C_PX_I`, `C_PY1_I`, `C_PY2_I`, `C_SEL_P` | offen | PX.*, PY1.1, PY2.1 |
| `C_COMP`, `C_COMP_I` | offen | PX.3 |
| `C_C_P` | offen | CP.1 |
| `C_O1`, `C_O2` | 01, 11 Quelle; 00 und 10 offen | CP.1, R.2 |
| `C_BR`, `C_SN` | Quelle (`IN7`, `IN1`) | R.1 |
| `C_2D_IN` | offen | R.1, R.2 |
| `C_CPE_CLK/EN/RES/SET`, `C_L_D`, `C_EN_SR`, `C_CLKSEL`, `C_ENSEL` | offen (nextpnr-Gebrauch angenommen) | R.1, R.2 |
| `C_RAM_I1/2`, `C_RAM_O1/2` | Polarität auffällig (M10), sonst offen | R.3 |

Ausgänge: `COUTX` (weit gemessen), `COUTY1` (Adder), `COUTY2`, `POUTX`, `POUTY1`, `POUTY2`, `CPOUT1/2` (offen), `OUT1`/`OUT2`/`RAM_O1/2` (Quelle).

## 8. Auswertung und Nachführung

- Pro Phase: Rohdaten nach `lab/cpe_rig/data/` kopieren (`resultsN.json`, fortlaufend ab 7), Reihe als `lab/cpe_rig/experiments/batchN.py` ablegen **nur nach Rückfrage**
  beim Nutzer (sonst im Arbeitsordner lassen und im Chat melden), Eintrag `M2x` in `hw_measurements.md`.
- `cpe.v` nachführen, `NOTE:` mit Verweis auf die Messung, danach `iverilog -g1995 -t null cpe.v`, `tb_adder.v`, `tb_bridge.v`, `tb_coutx.v` und ein neues `tb_*.v` für die Phase
  (Generator wie `lab/cpe_rig/make_tb_coutx.py`). `make_equiv_tb.py` zeigt die Abweichung des Modells vom Schematic; das ist erwartet.
- Nach jeder Phase eine Zusammenfassung an den Nutzer: bestätigt / abweichend / unklar, offene Fragen, Aufwand der nächsten Phase.

## 9. Aufwand (grob)

Phase 0: ca. 65 Läufe (16 min) plus Rig-Arbeit für Relais, Leser C und die Quellen für `CINY1/2`, `PINY1/2` im Wahrheitstabellen-Rig. Phase 1: ca. 110 Läufe (30 min). Phase 2: ca. 150 (40 min). Phase 3: ca. 150 (40 min). Phase 4: ca. 170 (45 min).
Phase 5-7: ca. 200 Läufe plus neue Basisdesigns (ADDF2, MULT) und ggf. weitere Leser im Wahrheitstabellen-Rig.

## 10. Anhang: Modellgleichungen (`cpe.v`), Stand heute

Mit `P = ~CADD_S`, `G = CADD_A` (siehe `cpe.v`), `route` = Mux {`C_SEL_C`/`C_SEL_P`, `C_SEL*`}:

    cx_route  {C_SEL_C,C_SELX} : 00 OUT1, 01 OUT2, 10 ~COMP_OUT (gemessen), 11 C_Y12 ? CINY2 : CINY1
    cy1_route {C_SEL_C,C_SELY1}: 00 OUT2, 01 OUT1, 10 COMP_OUT,             11 CINX
    cy2_route {C_SEL_C,C_SELY2}: 00 OUT1, 01 OUT2, 10 COMP_OUT,             11 CINX
    px_route  {C_SEL_P,C_SELX} : 00 OUT2, 01 OUT1, 10 COMP_OUT,             11 C_Y12 ? PINY2 : PINY1
    py1_route {C_SEL_P,C_SELY1}: 00 OUT1, 01 OUT2, 10 COMP_OUT,             11 PINX
    py2_route {C_SEL_P,C_SELY2}: 00 OUT2, 01 OUT1, 10 COMP_OUT,             11 PINX

    COUTX  = mux4({chain,alt}) 00 G, 01 cx_route, 10 CINX, 11 MULTO2;  chain = ~(C_CX_I | (C_ADDF & C_HORIZ & CADD_S)),  alt = C_MULT | C_CX_I        (gemessen)
    COUTY1 = through ? CINY1 : (cy1_adder ? G : cy1_route);  cy1_adder = C_ADDF & ~C_HORIZ;  through = ~(C_CY1_I | (cy1_adder & CADD_S))                (gemessen, C_HORIZ=0)
    COUTY2 = ((COY2_S | C_MULT) & C_CY2_I) ? CINY2 : (C_MULT ? COY2_a : cy2_route)                                                                       (Schematic, ungemessen)
    POUTX  = mux4({poutx_chain,poutx_alt}) 00 C_COMP_I, 01 px_route, 10 PINX, 11 MULTO1;  poutx_chain = (comp_out | (C_COMP & C_HORIZ)) & ~C_PX_I,  poutx_alt = C_MULT | C_PX_I   (Schematic)
    POUTY1 = ((comp_out | (C_COMP & ~C_HORIZ)) & C_PY1_I) ? PINY1 : ((C_COMP & ~C_HORIZ) ? C_COMP_I : py1_route)                                         (Schematic)
    POUTY2 = (C_PY2_I | C_MULT) ? PINY2 : py2_route                                                                                                        (Schematic)
    CPOUT1 = C_C_P ? carry : prop;  CPOUT2 = C_C_P ? prop : carry;  carry/prop = (C_HORIZ | C_MULT) ? (COUTX, POUTX) : (COUTY1, POUTY1)                   (Schematic)
