"""Minimal SCPI-over-TCP helper for Rigol MHO984 (192.168.2.165:5555). No dependencies."""
import socket, struct, sys, time

HOST, PORT = "192.168.2.165", 5555

class Scope:
    def __init__(self, host=HOST, port=PORT, timeout=10):
        self.s = socket.create_connection((host, port), timeout=timeout)
    def w(self, cmd): self.s.sendall((cmd + "\n").encode())
    def _readline(self):
        buf = b""
        while not buf.endswith(b"\n"): buf += self.s.recv(65536)
        return buf
    def q(self, cmd):
        self.w(cmd); return self._readline().decode().strip()
    def qf(self, cmd): return float(self.q(cmd))
    def qblock(self, cmd):
        """Query returning IEEE488.2 definite-length block (#9xxxxxxxxx...)."""
        self.w(cmd)
        buf = b""
        while len(buf) < 2: buf += self.s.recv(65536)
        assert buf[:1] == b"#", buf[:20]
        nd = int(buf[1:2]); 
        while len(buf) < 2 + nd: buf += self.s.recv(65536)
        n = int(buf[2:2+nd]); total = 2 + nd + n
        while len(buf) < total + 1: buf += self.s.recv(1 << 20)
        return buf[2+nd:total]
    def idn(self): return self.q("*IDN?")

    def setup_uart(self, tscale=1e-3, vscale=1.0, probe=10, mdepth=1000000, level=1.65, edge="NEG", src="CHAN1", offset_div=-1.5):
        """3.3V logic UART capture: ch1+ch2, edge trigger on falling start bit."""
        for ch in ("CHAN1", "CHAN2"):
            self.w(f":{ch}:DISP 1"); self.w(f":{ch}:COUP DC"); self.w(f":{ch}:PROB {probe}")
            self.w(f":{ch}:SCAL {vscale}"); self.w(f":{ch}:OFFS {-offset_div*vscale}")
        self.w(f":ACQ:MDEP {mdepth}")   # fixed! with AUTO the point count changes with the timebase
        self.w(f":TIM:MAIN:SCAL {tscale}"); self.w(":TIM:MAIN:OFFS 0")
        self.w(":TRIG:MODE EDGE"); self.w(f":TRIG:EDGE:SOUR {src}")
        self.w(f":TRIG:EDGE:SLOP {edge}"); self.w(f":TRIG:EDGE:LEV {level}")

    def run_auto(self):
        """Free-running AUTO sweep, only for live viewing / eyeballing. NOT for capturing data:
        a slow readout can mix samples of several trigger events. Use single() for captures."""
        self.w(":TRIG:SWEEP AUTO"); self.w(":RUN")

    def screenshot(self, path="shot.png"):
        b = self.qblock(":DISP:DATA? PNG"); open(path, "wb").write(b); return path

    def meas(self, item, ch="CHAN1"):
        """item e.g. VAVG VMAX VMIN VPP FREQ PER; 9.9E37 means 'no valid value'."""
        return self.qf(f":MEAS:ITEM? {item},{ch}")

    def single(self, timeout=10):
        """Stop, clear display/acq memory, arm single trigger, wait until stopped.
        Returns True if triggered. The :CLE avoids reading stale/mixed data from earlier triggers."""
        self.w(":STOP"); self.w(":CLE"); self.w(":SING")
        t0 = time.time()
        # Race: right after :SING the state may still read STOP -> first wait until armed (!= STOP)
        while self.q(":TRIG:STAT?") == "STOP":
            if time.time() - t0 > 0.3: break   # either it already triggered+finished, or it never armed
            time.sleep(0.02)
        while time.time() - t0 < timeout:
            if self.q(":TRIG:STAT?") == "STOP": return True
            time.sleep(0.05)
        self.w(":STOP"); return False

    def waveform(self, ch="CHAN1", points=None):
        """Return (t[], v[]) in seconds/volts from the stopped scope (RAW mode, BYTE)."""
        self.w(f":WAV:SOUR {ch}"); self.w(":WAV:MODE RAW"); self.w(":WAV:FORM BYTE")
        # default would return only a 125k-point fragment; ask for the whole acquisition memory
        want = points or int(self.qf(':ACQ:MDEP?'))
        for _ in range(5):   # scope sometimes ignores the first :WAV:POIN -> verify via preamble
            # reset the read window first: leftover STAR/STOP from the previous chunked read would shrink POIN
            self.w(":WAV:STAR 1"); self.w(f":WAV:STOP {want}"); self.w(f":WAV:POIN {want}")
            pre = self.q(":WAV:PRE?").split(",")
            if int(pre[2]) == want: break
        else: raise RuntimeError(f"scope returns {pre[2]} points, wanted {want}")
        n = int(pre[2]); xinc=float(pre[4]); xorg=float(pre[5]); xref=float(pre[6])
        yinc=float(pre[7]); yorg=float(pre[8]); yref=float(pre[9])
        raw = b""
        # read in chunks
        start = 1; chunk = 125000
        while start <= n:
            stop = min(start + chunk - 1, n)
            self.w(f":WAV:STAR {start}"); self.w(f":WAV:STOP {stop}")
            raw += self.qblock(":WAV:DATA?"); start = stop + 1
        v = [(b - yref - yorg) * yinc for b in raw]   # Rigol: (data - yorigin - yref)*yinc
        t = [(i - xref) * xinc + xorg for i in range(len(v))]
        return t, v

def decode_uart(t, v, baud=115200, thr=1.65, bits=8, parity=None):
    """Decode idle-high UART from sampled waveform; returns list of (time, byte)."""
    bit = 1.0 / baud; out = []; i = 0; n = len(v)
    dt = (t[-1] - t[0]) / (n - 1)
    def val(tt):
        k = int(round((tt - t[0]) / dt)); 
        return v[k] > thr if 0 <= k < n else None
    while i < n - 1:
        if v[i] > thr and v[i+1] <= thr:          # falling edge = start
            ts = t[i] + dt/2
            if val(ts + bit/2) is False:
                d = 0; ok = True
                for b in range(bits):
                    x = val(ts + bit*(1.5+b))
                    if x is None: ok = False; break
                    d |= int(x) << b
                stop = val(ts + bit*(1.5+bits))
                if ok and stop: out.append((ts, d))
                i += int(bit*(bits+1)/dt)
        i += 1
    return out

if __name__ == "__main__":
    s = Scope(); print(s.idn())
