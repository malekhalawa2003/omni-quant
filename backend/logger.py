import json
import threading
import time
from pathlib import Path

from .shared_state import state


class Logger:
    def __init__(self, log_dir: str = "logs"):
        self._dir  = Path(log_dir)
        self._dir.mkdir(exist_ok=True)
        self._file = self._dir / f"omni_{time.strftime('%Y%m%d_%H%M%S')}.jsonl"
        self._lock = threading.Lock()

    # ── Public API ────────────────────────────────────────────────────────

    def log(self, level: str, message: str, data: dict = None):
        entry = {
            "timestamp": time.time(),
            "datetime":  time.strftime("%Y-%m-%d %H:%M:%S"),
            "level":     level,
            "message":   message,
            "data":      data or {},
        }
        with self._lock:
            with open(self._file, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry) + "\n")
        state.add_log(level, message, data)

    def log_trade(self, trade: dict):
        self.log("TRADE", f"Trade closed — PnL ${trade.get('pnl', 0):+.2f}", trade)

    def log_signal(self, strategy: str, signal: int, prob: float):
        direction = "LONG" if signal > 0 else ("SHORT" if signal < 0 else "FLAT")
        self.log("SIGNAL", f"{strategy}: {direction} ({prob:.1%})")

    @property
    def log_file(self) -> str:
        return str(self._file)


logger = Logger()
