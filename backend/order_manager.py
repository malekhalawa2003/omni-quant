import random
import threading
import time
import uuid

from .shared_state import state


class OrderManager:
    def __init__(self):
        self._running = False
        self._thread: threading.Thread = None

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="OrderManager"
        )
        self._thread.start()

    def stop(self):
        self._running = False

    # ── Order placement ───────────────────────────────────────────────────

    def place_order(self, side: str, size: float,
                    order_type: str = "MARKET") -> str | None:
        with state.acquire():
            if not state.trading_active:
                state.add_log("WARN", "Order rejected: trading not active")
                return None
            if any(state.circuit_breakers.values()):
                state.add_log("WARN", "Order rejected: circuit breaker active")
                return None
            live = state.live_trading

        order = {
            "id":         str(uuid.uuid4())[:8].upper(),
            "side":       side,
            "size":       size,
            "type":       order_type,
            "status":     "PENDING",
            "created_at": time.time(),
            "fill_price": None,
            "slippage":   None,
            "mode":       "LIVE" if live else "PAPER",
        }

        with state.acquire():
            state.pending_orders.append(order)
            state.add_log(
                "INFO",
                f"{'🔴 LIVE' if live else '📄 PAPER'} order: "
                f"{side.upper()} {size:.4f} @ {order_type}",
                {"id": order["id"]},
            )

        target = self._live_fill if live else self._paper_fill
        threading.Thread(target=target, args=(order,), daemon=True).start()
        return order["id"]

    # ── Emergency stop ────────────────────────────────────────────────────

    def emergency_stop(self):
        with state.acquire():
            live = state.live_trading
            pos  = dict(state.position)

        if live and pos["side"]:
            self._live_close_position(pos)
        else:
            self._paper_emergency_stop()

        state.add_log("CRITICAL", "🚨 EMERGENCY STOP — all positions closed")

    def _live_close_position(self, pos: dict):
        from .exchange import exchange
        try:
            sym = exchange.to_ccxt_symbol(state.symbol)
            exchange.close_position(sym, pos["side"], pos["size"])
        except Exception as exc:
            state.add_log("ERROR", f"Live emergency close failed: {exc}")
        finally:
            self._apply_stop_to_state()

    def _paper_emergency_stop(self):
        with state.acquire():
            for o in state.pending_orders:
                o["status"] = "CANCELLED"
                state.rejected_orders.append(o)
            state.pending_orders.clear()
        self._apply_stop_to_state()

    def _apply_stop_to_state(self):
        with state.acquire():
            state.trading_active    = False
            state.emergency_stopped = True
            state.circuit_breakers["manual_stop"] = True

            if state.position["side"]:
                pnl = state.position["unrealized_pnl"]
                state.daily_pnl += pnl
                state.session_trades.append({
                    "time":   time.strftime("%H:%M:%S"),
                    "side":   state.position["side"],
                    "entry":  state.position["entry_price"],
                    "exit":   state.ticker["price"],
                    "size":   state.position["size"],
                    "pnl":    round(pnl, 2),
                    "reason": "EMERGENCY_STOP",
                })
                state.position = {
                    "side": None, "size": 0.0,
                    "entry_price": 0.0, "unrealized_pnl": 0.0,
                }

    # ── Live fill (real exchange) ─────────────────────────────────────────

    def _live_fill(self, order: dict):
        from .exchange import exchange
        try:
            sym    = exchange.to_ccxt_symbol(state.symbol)
            result = exchange.place_order(sym, order["side"], order["size"])

            fill_price = float(
                result.get("average") or result.get("price")
                or state.ticker["price"]
            )
            slip = abs(fill_price - state.ticker["price"]) * order["size"]

            with state.acquire():
                order["fill_price"]  = round(fill_price, 4)
                order["slippage"]    = round(slip, 4)
                order["status"]      = "FILLED"
                order["filled_at"]   = time.time()
                order["exchange_id"] = result.get("id", "")

                state.pending_orders[:] = [
                    o for o in state.pending_orders if o["id"] != order["id"]
                ]
                state.filled_orders.append(order)
                state.slippage_records.append(slip)

            # Sync real position from exchange
            self._sync_position(exchange, sym, order)

            state.add_log(
                "TRADE",
                f"✅ LIVE fill: {order['side'].upper()} {order['size']} "
                f"@ ${fill_price:,.4f}",
                {"id": order["id"], "exchange_id": result.get("id", "")},
            )

        except Exception as exc:
            with state.acquire():
                order["status"]        = "REJECTED"
                order["reject_reason"] = str(exc)
                state.pending_orders[:] = [
                    o for o in state.pending_orders if o["id"] != order["id"]
                ]
                state.rejected_orders.append(order)
            state.add_log("ERROR", f"Live order failed: {exc}")

    def _sync_position(self, exchange, ccxt_symbol: str, order: dict):
        try:
            positions = exchange.fetch_positions(ccxt_symbol)
            for pos in positions:
                contracts = abs(float(pos.get("contracts") or 0))
                if pos.get("symbol") == ccxt_symbol and contracts > 0:
                    with state.acquire():
                        state.position = {
                            "side":          pos["side"],
                            "size":          contracts,
                            "entry_price":   float(pos.get("entryPrice") or 0),
                            "unrealized_pnl": float(pos.get("unrealizedPnl") or 0),
                        }
                    return
            # Flat
            with state.acquire():
                if state.position["side"]:
                    pnl = state.position["unrealized_pnl"]
                    state.daily_pnl += pnl
                    state.session_trades.append({
                        "time":  time.strftime("%H:%M:%S"),
                        "side":  state.position["side"],
                        "entry": state.position["entry_price"],
                        "exit":  state.ticker["price"],
                        "size":  state.position["size"],
                        "pnl":   round(pnl, 2),
                    })
                state.position = {
                    "side": None, "size": 0.0,
                    "entry_price": 0.0, "unrealized_pnl": 0.0,
                }
        except Exception as exc:
            state.add_log("WARN", f"Position sync failed: {exc}")

    # ── Paper fill (simulation) ───────────────────────────────────────────

    def _paper_fill(self, order: dict):
        time.sleep(random.uniform(0.05, 0.35))

        with state.acquire():
            price = state.ticker["price"]
            if price == 0:
                order["status"]        = "REJECTED"
                order["reject_reason"] = "No market price"
                state.pending_orders[:] = [
                    o for o in state.pending_orders if o["id"] != order["id"]
                ]
                state.rejected_orders.append(order)
                return

            slip_pct   = random.uniform(-0.0002, 0.0005)
            fill_price = price * (1 + slip_pct)
            slip_usd   = abs(slip_pct) * price * order["size"]

            order["fill_price"] = round(fill_price, 4)
            order["slippage"]   = round(slip_usd, 4)
            order["status"]     = "FILLED"
            order["filled_at"]  = time.time()

            state.pending_orders[:] = [
                o for o in state.pending_orders if o["id"] != order["id"]
            ]
            state.filled_orders.append(order)
            state.slippage_records.append(slip_usd)

            pos = state.position
            if pos["side"] is None:
                pos["side"]           = order["side"]
                pos["size"]           = order["size"]
                pos["entry_price"]    = fill_price
                pos["unrealized_pnl"] = 0.0
            else:
                pnl = pos["unrealized_pnl"]
                state.daily_pnl += pnl
                state.session_trades.append({
                    "time":  time.strftime("%H:%M:%S"),
                    "side":  pos["side"],
                    "entry": pos["entry_price"],
                    "exit":  fill_price,
                    "size":  pos["size"],
                    "pnl":   round(pnl, 2),
                })
                state.position = {
                    "side": None, "size": 0.0,
                    "entry_price": 0.0, "unrealized_pnl": 0.0,
                }

            state.add_log(
                "TRADE",
                f"📄 Paper fill: {order['side'].upper()} {order['size']} "
                f"@ ${fill_price:,.4f} (slip ${slip_usd:.4f})",
            )

    def _run(self):
        while self._running:
            time.sleep(5)


order_manager = OrderManager()
