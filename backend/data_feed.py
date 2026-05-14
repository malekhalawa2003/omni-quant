import asyncio
import json
import threading
import time

import websockets

from .shared_state import Candle, state

_BINANCE_WS = "wss://stream.binance.com:9443/stream"


class BinanceDataFeed:
    def __init__(self):
        self._loop: asyncio.AbstractEventLoop = None
        self._thread: threading.Thread = None
        self._running = False
        self._backoff = 3

    # ── Public API ────────────────────────────────────────────────────────

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._run_loop, daemon=True, name="BinanceFeed"
        )
        self._thread.start()

    def stop(self):
        self._running = False
        if self._loop and not self._loop.is_closed():
            self._loop.call_soon_threadsafe(self._loop.stop)

    def restart(self, symbol: str = None, timeframe: str = None):
        with state.acquire():
            if symbol:
                state.symbol = symbol
            if timeframe:
                state.timeframe = timeframe
        self.stop()
        time.sleep(0.3)
        self.start()

    # ── Internal ──────────────────────────────────────────────────────────

    def _run_loop(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._connect())
        except Exception as exc:
            state.add_log("ERROR", f"Feed loop crashed: {exc}")
        finally:
            with state.acquire():
                state.connected = False

    async def _connect(self):
        while self._running:
            sym = state.symbol.lower()
            tf  = state.timeframe
            streams = (
                f"{sym}@kline_{tf}"
                f"/{sym}@bookTicker"
                f"/{sym}@miniTicker"
                f"/{sym}@depth5@100ms"
            )
            url = f"{_BINANCE_WS}?streams={streams}"

            try:
                async with websockets.connect(
                    url, ping_interval=20, ping_timeout=10
                ) as ws:
                    with state.acquire():
                        state.connected = True
                    state.add_log("INFO", f"Connected: {sym.upper()} {tf}")
                    self._backoff = 3

                    async for raw in ws:
                        if not self._running:
                            break
                        try:
                            self._process(json.loads(raw))
                        except Exception:
                            pass

            except Exception as exc:
                with state.acquire():
                    state.connected = False
                state.add_log(
                    "WARN",
                    f"Disconnected ({type(exc).__name__}). Retry in {self._backoff}s",
                )
                await asyncio.sleep(self._backoff)
                self._backoff = min(self._backoff * 2, 30)

    def _process(self, msg: dict):
        stream = msg.get("stream", "")
        data   = msg.get("data", {})

        if "@kline" in stream:
            k = data["k"]
            state.update_candle(Candle(
                time=k["t"] // 1000,
                open=float(k["o"]),
                high=float(k["h"]),
                low=float(k["l"]),
                close=float(k["c"]),
                volume=float(k["v"]),
                is_closed=k["x"],
            ))

        elif "@bookTicker" in stream:
            with state.acquire():
                state.ticker["bid"] = float(data["b"])
                state.ticker["ask"] = float(data["a"])
                state.ticker["price"] = (
                    state.ticker["bid"] + state.ticker["ask"]
                ) / 2
                state.ticker["last_update"] = time.time()

        elif "@miniTicker" in stream:
            with state.acquire():
                state.ticker["high_24h"]          = float(data["h"])
                state.ticker["low_24h"]           = float(data["l"])
                state.ticker["volume_24h"]        = float(data["v"])
                state.ticker["price_change_pct"]  = float(data["P"])

        elif "@depth5" in stream:
            with state.acquire():
                state.orderbook["bids"] = [
                    [float(p), float(q)] for p, q in data.get("bids", [])
                ]
                state.orderbook["asks"] = [
                    [float(p), float(q)] for p, q in data.get("asks", [])
                ]


feed = BinanceDataFeed()
