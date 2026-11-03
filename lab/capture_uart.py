"""Usage: python capture_uart.py [baud] [timebase_s_per_div]
Single-shot capture, falling-edge trigger on CH1 (UART0_TX), decode CH1 (TX) and CH2 (RX)."""
import sys; from scope import *
baud = int(sys.argv[1]) if len(sys.argv) > 1 else 115200
tb = float(sys.argv[2]) if len(sys.argv) > 2 else 1e-3
s = Scope(); s.setup_uart(tscale=tb)
if not s.single(timeout=10): print("NO TRIGGER (no start bit seen on CH1)"); sys.exit(1)
for name, ch in (("TX/CH1", "CHAN1"), ("RX/CH2", "CHAN2")):
    t, v = s.waveform(ch); r = decode_uart(t, v, baud)
    print(name, bytes(b for _, b in r))
