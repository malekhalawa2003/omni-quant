"""
Auto-trading engine for OmniQuant.

Entry:  when confluence threshold is met (3+ strategies agree) and no position is open.
Exit:   stop-loss, take-profit, or signal reversal — whichever triggers first.
Sizing: risk_per_trade_pct % of current equity, capped by position_size_cap.
"""
import threading
import time

from .shared_state import state


class AutoTrader:
    def __init__(self):
        self._thread: threading.Thread = None
        self._running = False
        self._entry_cooldown = 0      # bars to wait after a trade

    # ── Lifecycle ─────────────────────────────────────────────────────────

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="AutoTrader"
        )
        self._thread.start()

    def stop(self):
        self._running = False

    # ── Main loop ─────────────────────────────────────────────────────────

    def _run(self):
        while self._running:
            try:
                with state.acquire():
                    active    = state.trading_active
                    auto      = state.auto_trade
                    any_cb    = any(state.circuit_breakers.values())
                    connected = state.connected

                if active and auto and not any_cb and connected:
                    self._tick()

            except Exception as exc:
                state.add_log("ERROR", f"AutoTrader: {exc}")

            time.sleep(1)

    def _tick(self):
        if self._entry_cooldown > 0:
            self._entry_cooldown -= 1

        with state.acquire():
            has_pos    = state.position["side"] is not None
            confluence = state.confluence_met
            ensemble   = state.ensemble_signal

        if has_pos:
            self._check_exit()
        elif confluence and ensemble != 0 and self._entry_cooldown == 0:
            self._enter(ensemble)

    # ── Entry ─────────────────────────────────────────────────────────────

    def _enter(self, signal: int):
        side = "long" if signal == 1 else "short"
        size = self._calc_size()
        if size <= 0:
            state.add_log("WARN", "AutoTrader: size calc returned 0, skipping entry")
            return

        from .order_manager import order_manager
        oid = order_manager.place_order(side, size)
        if oid:
            state.add_log(
                "INFO",
                f"AutoTrader: ENTER {side.upper()} size={size:.4f}",
                {"order_id": oid},
            )
            self._entry_cooldown = 5  # minimum 5s between trades

    # ── Exit ──────────────────────────────────────────────────────────────

    def _check_exit(self):
        with state.acquire():
            pos       = dict(state.position)
            sl_pct    = state.stop_loss_pct
            tp_pct    = state.take_profit_pct
            confluence = state.confluence_met
            ensemble  = state.ensemble_signal

        if not pos["side"] or pos["entry_price"] == 0 or pos["size"] == 0:
            return

        cost    = pos["entry_price"] * pos["size"]
        upnl_pct = (pos["unrealized_pnl"] / cost * 100) if cost else 0

        reason = None

        if upnl_pct <= -sl_pct:
            reason = f"stop-loss ({upnl_pct:.2f}%)"
        elif upnl_pct >= tp_pct:
            reason = f"take-profit ({upnl_pct:.2f}%)"
        elif confluence and ensemble != 0:
            current_dir = 1 if pos["side"] == "long" else -1
            if ensemble != current_dir:
                reason = f"signal reversal → {'LONG' if ensemble == 1 else 'SHORT'}"

        if reason:
            exit_side = "short" if pos["side"] == "long" else "long"
            from .order_manager import order_manager
            order_manager.place_order(exit_side, pos["size"])
            state.add_log("INFO", f"AutoTrader: EXIT — {reason}")
            self._entry_cooldown = 5

    # ── Position sizing ───────────────────────────────────────────────────

    def _calc_size(self) -> float:
        with state.acquire():
            equity   = state.current_equity
            risk_pct = state.risk_per_trade_pct / 100
            price    = state.ticker["price"]
            sz_cap   = state.position_size_cap

        if price == 0:
            return 0.0

        risk_usd = equity * risk_pct
        size     = risk_usd / price
        max_size = sz_cap / price
        return round(min(size, max_size), 4)


auto_trader = AutoTrader()
