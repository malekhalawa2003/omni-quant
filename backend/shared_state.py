import os
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Dict, List


@dataclass
class Candle:
    time: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    is_closed: bool = False


class SharedState:
    def __init__(self):
        self._lock = threading.RLock()

        # Market data
        self._candles: Dict[str, deque] = {}
        self.ticker = {
            "symbol": "BTCUSDT",
            "price": 0.0,
            "bid": 0.0,
            "ask": 0.0,
            "high_24h": 0.0,
            "low_24h": 0.0,
            "volume_24h": 0.0,
            "price_change_pct": 0.0,
            "last_update": 0.0,
        }
        self.orderbook: Dict[str, list] = {"bids": [], "asks": []}

        # Connection
        self.connected = False
        self.symbol = "BTCUSDT"
        self.timeframe = "1m"

        # ── Trading mode ──────────────────────────────────────────────────
        self.live_trading = False       # False = paper, True = live exchange
        self.live_connected = False     # exchange API connected
        self.account_balance = float(os.getenv("STARTING_EQUITY", "10000"))

        # ── Trading controls ──────────────────────────────────────────────
        self.trading_active = False
        self.emergency_stopped = False

        # ── Auto-trader settings ──────────────────────────────────────────
        self.auto_trade = False
        self.stop_loss_pct = 2.0        # % of entry price
        self.take_profit_pct = 4.0      # % of entry price
        self.risk_per_trade_pct = 1.0   # % of equity risked per trade

        # ── Position (paper or synced from exchange) ──────────────────────
        self.position = {
            "side": None,              # "long" | "short" | None
            "size": 0.0,
            "entry_price": 0.0,
            "unrealized_pnl": 0.0,
        }

        # ── P&L ──────────────────────────────────────────────────────────
        self.daily_pnl = 0.0
        self.max_drawdown = 0.0
        self.peak_equity = self.account_balance
        self.current_equity = self.account_balance

        # ── Risk params ───────────────────────────────────────────────────
        self.daily_loss_limit = 500.0
        self.position_size_cap = 1_000.0

        # ── Strategies ───────────────────────────────────────────────────
        self.strategies = {
            "RSI Momentum":      {"enabled": True, "signal": 0, "win_prob": 0.5},
            "MACD Cross":        {"enabled": True, "signal": 0, "win_prob": 0.5},
            "BB Squeeze":        {"enabled": True, "signal": 0, "win_prob": 0.5},
            "Volume Profile":    {"enabled": True, "signal": 0, "win_prob": 0.5},
            "Order Flow Imbal.": {"enabled": True, "signal": 0, "win_prob": 0.5},
        }
        self.ensemble_signal = 0
        self.confluence_met = False

        # ── Orders ───────────────────────────────────────────────────────
        self.pending_orders: List[dict] = []
        self.filled_orders:  List[dict] = []
        self.rejected_orders: List[dict] = []
        self.slippage_records: List[float] = []

        # Closed trades
        self.session_trades: List[dict] = []

        # ── Performance ───────────────────────────────────────────────────
        self.performance = {
            "sharpe": 0.0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "max_consec_wins": 0,
            "max_consec_losses": 0,
            "current_streak": 0,
        }

        # ── Circuit breakers ──────────────────────────────────────────────
        self.circuit_breakers = {
            "daily_loss_triggered": False,
            "mdd_triggered": False,
            "manual_stop": False,
        }

        # In-dashboard log tail
        self.log_entries: deque = deque(maxlen=50)

    # ── Thread safety ─────────────────────────────────────────────────────

    def acquire(self):
        return self._lock

    # ── Candle helpers ────────────────────────────────────────────────────

    def update_candle(self, candle: Candle):
        with self._lock:
            key = self.symbol
            if key not in self._candles:
                self._candles[key] = deque(maxlen=500)
            buf = self._candles[key]
            if buf and buf[-1].time == candle.time:
                buf[-1] = candle
            else:
                buf.append(candle)

    def get_candles(self, limit: int = 200) -> List[Candle]:
        with self._lock:
            return list(self._candles.get(self.symbol, []))[-limit:]

    # ── Logging ───────────────────────────────────────────────────────────

    def add_log(self, level: str, message: str, data: dict = None):
        with self._lock:
            self.log_entries.append({
                "time": time.time(),
                "datetime": time.strftime("%H:%M:%S"),
                "level": level,
                "message": message,
                "data": data or {},
            })

    # ── Circuit breakers ──────────────────────────────────────────────────

    def check_circuit_breakers(self):
        with self._lock:
            if (self.daily_pnl <= -self.daily_loss_limit
                    and not self.circuit_breakers["daily_loss_triggered"]):
                self.circuit_breakers["daily_loss_triggered"] = True
                self.trading_active = False
                self.log_entries.append({
                    "time": time.time(),
                    "datetime": time.strftime("%H:%M:%S"),
                    "level": "CRITICAL",
                    "message": f"CIRCUIT BREAKER: daily loss ${self.daily_loss_limit:.0f} hit",
                    "data": {},
                })

            if (self.max_drawdown >= 20.0
                    and not self.circuit_breakers["mdd_triggered"]):
                self.circuit_breakers["mdd_triggered"] = True
                self.trading_active = False
                self.log_entries.append({
                    "time": time.time(),
                    "datetime": time.strftime("%H:%M:%S"),
                    "level": "CRITICAL",
                    "message": "CIRCUIT BREAKER: max drawdown 20% hit",
                    "data": {},
                })


state = SharedState()
