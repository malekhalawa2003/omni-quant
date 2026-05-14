import threading
import time

import numpy as np

from .shared_state import state


class RiskEngine:
    def __init__(self):
        self._thread: threading.Thread = None
        self._running = False
        self._tick = 0

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="RiskEngine"
        )
        self._thread.start()

    def stop(self):
        self._running = False

    def _run(self):
        while self._running:
            self._update_pnl()
            self._update_performance()
            state.check_circuit_breakers()

            # Sync exchange balance every 15 s in live mode
            if self._tick % 15 == 0:
                self._sync_balance()

            self._tick += 1
            time.sleep(1)

    # ── P&L & drawdown ───────────────────────────────────────────────────

    def _update_pnl(self):
        with state.acquire():
            pos   = state.position
            price = state.ticker["price"]

            # In live mode, unrealized_pnl is synced from exchange;
            # in paper mode we compute it ourselves.
            if pos["side"] and price > 0 and not state.live_trading:
                entry = pos["entry_price"]
                size  = pos["size"]
                pos["unrealized_pnl"] = (
                    (price - entry) * size if pos["side"] == "long"
                    else (entry - price) * size
                )

            if pos["side"]:
                equity = state.peak_equity + state.daily_pnl + pos["unrealized_pnl"]
            else:
                equity = state.peak_equity + state.daily_pnl

            state.current_equity = equity
            if equity > state.peak_equity:
                state.peak_equity = equity

            dd = (state.peak_equity - equity) / state.peak_equity * 100 if state.peak_equity > 0 else 0
            state.max_drawdown = max(state.max_drawdown, dd)

    # ── Performance metrics ──────────────────────────────────────────────

    def _update_performance(self):
        with state.acquire():
            trades = state.session_trades
            if not trades:
                return

            pnls   = [t["pnl"] for t in trades]
            wins   = [p for p in pnls if p > 0]
            losses = [p for p in pnls if p <= 0]

            state.performance["win_rate"] = len(wins) / len(pnls)

            total_win  = sum(wins)
            total_loss = abs(sum(losses))
            state.performance["profit_factor"] = (
                total_win / total_loss if total_loss > 0 else float("inf")
            )

            recent = pnls[-20:]
            if len(recent) >= 2:
                mu    = np.mean(recent)
                sigma = np.std(recent)
                state.performance["sharpe"] = (
                    float(mu / sigma * np.sqrt(252)) if sigma > 0 else 0.0
                )

            # Streak
            max_w = max_l = cur = 1
            for i in range(1, len(pnls)):
                if (pnls[i] > 0) == (pnls[i - 1] > 0):
                    cur += 1
                else:
                    cur = 1
                if pnls[i] > 0:
                    max_w = max(max_w, cur)
                else:
                    max_l = max(max_l, cur)

            tail = 1
            for i in range(len(pnls) - 2, -1, -1):
                if (pnls[i] > 0) == (pnls[-1] > 0):
                    tail += 1
                else:
                    break

            state.performance["max_consec_wins"]   = max_w
            state.performance["max_consec_losses"] = max_l
            state.performance["current_streak"]    = tail if pnls[-1] > 0 else -tail

    # ── Balance sync (live only) ─────────────────────────────────────────

    def _sync_balance(self):
        with state.acquire():
            live      = state.live_trading
            connected = state.live_connected
        if not live or not connected:
            return
        try:
            from .exchange import exchange
            bal = exchange.fetch_balance()
            with state.acquire():
                state.account_balance = bal
                if not state.position["side"]:
                    state.current_equity = bal
        except Exception:
            pass


risk_engine = RiskEngine()
