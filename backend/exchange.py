"""
Real exchange client (Binance futures via ccxt).
Falls back gracefully when no API keys are set.
"""
import os
import threading

import ccxt
from dotenv import load_dotenv

from .shared_state import state

load_dotenv()


class ExchangeClient:
    def __init__(self):
        self._client: ccxt.binance = None
        self._lock = threading.Lock()
        self.error: str = None

    # ── Connection ────────────────────────────────────────────────────────

    def connect(self, api_key: str = None, secret: str = None, testnet: bool = None) -> bool:
        key    = api_key or os.getenv("BINANCE_API_KEY", "")
        sec    = secret  or os.getenv("BINANCE_SECRET",  "")
        is_testnet = testnet if testnet is not None else (
            os.getenv("BINANCE_TESTNET", "true").lower() == "true"
        )

        if not key or not sec:
            self.error = "No API keys — running in paper mode"
            state.add_log("WARN", self.error)
            return False

        try:
            params: dict = {
                "apiKey": key,
                "secret": sec,
                "options": {"defaultType": "future"},
                "enableRateLimit": True,
            }
            if is_testnet:
                params["urls"] = {
                    "api": {
                        "public":  "https://testnet.binancefuture.com/fapi/v1",
                        "private": "https://testnet.binancefuture.com/fapi/v1",
                    }
                }

            client = ccxt.binance(params)
            balance = client.fetch_balance()

            with self._lock:
                self._client = client

            usdt = float(balance.get("total", {}).get("USDT", 0))
            with state.acquire():
                state.account_balance = usdt
                state.current_equity  = usdt
                state.peak_equity     = max(state.peak_equity, usdt)
                state.live_connected  = True

            mode = "TESTNET" if is_testnet else "⚠️  LIVE MAINNET"
            state.add_log("INFO", f"Exchange connected [{mode}] — Balance: ${usdt:,.2f} USDT")
            self.error = None
            return True

        except Exception as exc:
            self.error = str(exc)
            with state.acquire():
                state.live_connected = False
            state.add_log("ERROR", f"Exchange connection failed: {exc}")
            return False

    def disconnect(self):
        with self._lock:
            self._client = None
        with state.acquire():
            state.live_connected = False
        state.add_log("INFO", "Exchange disconnected")

    @property
    def is_connected(self) -> bool:
        with self._lock:
            return self._client is not None

    # ── Orders ────────────────────────────────────────────────────────────

    def place_order(self, symbol: str, side: str, amount: float,
                    order_type: str = "market") -> dict:
        with self._lock:
            if not self._client:
                raise RuntimeError("Exchange not connected")
            ccxt_side = "buy" if side in ("long", "buy") else "sell"
            return self._client.create_order(symbol, order_type, ccxt_side, amount)

    def close_position(self, symbol: str, side: str, amount: float):
        with self._lock:
            if not self._client:
                return
            close_side = "sell" if side == "long" else "buy"
            self._client.create_order(
                symbol, "market", close_side, amount,
                {"reduceOnly": True},
            )

    def cancel_order(self, order_id: str, symbol: str):
        with self._lock:
            if not self._client:
                return
            self._client.cancel_order(order_id, symbol)

    # ── Account data ──────────────────────────────────────────────────────

    def fetch_balance(self) -> float:
        with self._lock:
            if not self._client:
                return state.account_balance
            bal = self._client.fetch_balance()
            return float(bal.get("total", {}).get("USDT", 0))

    def fetch_positions(self, symbol: str = None) -> list:
        with self._lock:
            if not self._client:
                return []
            return self._client.fetch_positions([symbol] if symbol else None)

    # ── Symbol formatting ─────────────────────────────────────────────────

    @staticmethod
    def to_ccxt_symbol(symbol: str) -> str:
        """BTCUSDT → BTC/USDT:USDT  (Binance futures format)"""
        base = symbol.replace("USDT", "")
        return f"{base}/USDT:USDT"


exchange = ExchangeClient()
