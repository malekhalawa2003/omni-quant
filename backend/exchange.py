"""
OKX exchange client via ccxt.
OKX requires three credentials: API Key, Secret, and Passphrase.
"""
import os
import threading

import ccxt
from dotenv import load_dotenv

from .shared_state import state

load_dotenv()


class ExchangeClient:
    def __init__(self):
        self._client: ccxt.okx = None
        self._lock = threading.Lock()
        self.error: str = None

    # ── Connection ────────────────────────────────────────────────────────

    def connect(self, api_key: str = None, secret: str = None,
                passphrase: str = None, testnet: bool = None) -> bool:
        key   = api_key    or os.getenv("OKX_API_KEY",    "")
        sec   = secret     or os.getenv("OKX_SECRET",     "")
        passw = passphrase or os.getenv("OKX_PASSPHRASE", "")
        is_demo = testnet if testnet is not None else (
            os.getenv("OKX_TESTNET", "true").lower() == "true"
        )

        if not key or not sec or not passw:
            self.error = "OKX requires API Key, Secret, and Passphrase"
            state.add_log("WARN", self.error)
            return False

        try:
            params = {
                "apiKey":   key,
                "secret":   sec,
                "password": passw,
                "options":  {"defaultType": "swap"},
                "enableRateLimit": True,
            }

            client = ccxt.okx(params)
            if is_demo:
                client.set_sandbox_mode(True)
            balance = client.fetch_balance()

            with self._lock:
                self._client = client

            usdt = float(balance.get("total", {}).get("USDT", 0))
            with state.acquire():
                state.account_balance = usdt
                state.current_equity  = usdt
                state.peak_equity     = max(state.peak_equity, usdt)
                state.live_connected  = True

            mode = "DEMO" if is_demo else "⚠️  LIVE"
            state.add_log("INFO", f"OKX [{mode}] connected — ${usdt:,.2f} USDT")
            self.error = None
            return True

        except Exception as exc:
            self.error = str(exc)
            with state.acquire():
                state.live_connected = False
            state.add_log("ERROR", f"OKX connection failed: {exc}")
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
            return self._client.create_order(
                self.to_ccxt_symbol(symbol), order_type, ccxt_side, amount
            )

    def close_position(self, symbol: str, side: str, amount: float):
        with self._lock:
            if not self._client:
                return
            close_side = "sell" if side == "long" else "buy"
            self._client.create_order(
                self.to_ccxt_symbol(symbol), "market", close_side, amount,
                {"reduceOnly": True},
            )

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
            syms = [self.to_ccxt_symbol(symbol)] if symbol else None
            return self._client.fetch_positions(syms)

    # ── Symbol helpers ────────────────────────────────────────────────────

    @staticmethod
    def to_ccxt_symbol(symbol: str) -> str:
        """BTC-USDT → BTC/USDT:USDT  (OKX perpetual swap format)"""
        base = symbol.replace("-USDT", "")
        return f"{base}/USDT:USDT"


exchange = ExchangeClient()
