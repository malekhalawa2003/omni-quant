import asyncio
import json
import threading
import time

import websockets

from .shared_state import Candle, state

_WS_PUBLIC   = "wss://ws.okx.com:8443/ws/v5/public"
_WS_BUSINESS = "wss://ws.okx.com:8443/ws/v5/business"
_REST_CANDLES = "https://www.okx.com/api/v5/market/candles"

_TF_MAP = {
    "1m":  "candle1m",
    "5m":  "candle5m",
    "15m": "candle15m",
    "1h":  "candle1H",
}

_REST_TF_MAP = {
    "1m":  "1m",
    "5m":  "5m",
    "15m": "15m",
    "1h":  "1H",
}


class OKXDataFeed:
    def __init__(self):
        self._loop: asyncio.AbstractEventLoop = None
        self._thread: threading.Thread = None
        self._running = False
        self._backoff = 3

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._run_loop, daemon=True, name="OKXFeed"
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

    # ── Historical seed via REST ──────────────────────────────────────────

    def _seed_candles(self, inst_id: str, timeframe: str):
        """Fetch last 100 closed candles from REST so strategies have data immediately."""
        import requests, urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        tf = _REST_TF_MAP.get(timeframe, "1m")
        url = f"{_REST_CANDLES}?instId={inst_id}&bar={tf}&limit=100"
        try:
            resp = requests.get(url, timeout=8, verify=False,
                               headers={"User-Agent": "OmniQuant/1.0"})
            rows = resp.json().get("data", [])
            # REST returns newest-first; reverse to get oldest-first
            for row in reversed(rows):
                # [ts_ms, open, high, low, close, vol, volCcy, volCcyQuote, confirm]
                state.update_candle(Candle(
                    time=int(row[0]) // 1000,
                    open=float(row[1]),
                    high=float(row[2]),
                    low=float(row[3]),
                    close=float(row[4]),
                    volume=float(row[5]),
                    is_closed=(row[8] == "1") if len(row) > 8 else True,
                ))
            n = len(state.get_candles())
            state.add_log("INFO", f"Seeded {n} candles from REST for {inst_id}")
        except Exception as exc:
            state.add_log("WARN", f"REST seed failed ({exc}); waiting for WS data")

    # ── Event loop ────────────────────────────────────────────────────────

    def _run_loop(self):
        inst_id  = state.symbol
        timeframe = state.timeframe
        # Seed candle history before starting WS
        self._seed_candles(inst_id, timeframe)

        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._connect())
        except Exception as exc:
            state.add_log("ERROR", f"Feed loop crashed: {exc}")
        finally:
            with state.acquire():
                state.connected = False

    # ── WebSocket ─────────────────────────────────────────────────────────

    async def _connect(self):
        while self._running:
            inst_id = state.symbol
            tf_key  = _TF_MAP.get(state.timeframe, "candle1m")

            sub_public = json.dumps({
                "op": "subscribe",
                "args": [
                    {"channel": "tickers", "instId": inst_id},
                    {"channel": "books5",  "instId": inst_id},
                ],
            })
            sub_business = json.dumps({
                "op": "subscribe",
                "args": [{"channel": tf_key, "instId": inst_id}],
            })

            try:
                with state.acquire():
                    state.connected = True
                state.add_log("INFO", f"OKX WS connected: {inst_id} {state.timeframe}")
                self._backoff = 3

                await asyncio.gather(
                    self._stream(_WS_PUBLIC,   sub_public),
                    self._stream(_WS_BUSINESS, sub_business),
                    return_exceptions=True,
                )

            except Exception as exc:
                pass
            finally:
                with state.acquire():
                    state.connected = False
                state.add_log(
                    "WARN",
                    f"WS disconnected. Retry in {self._backoff}s",
                )
                await asyncio.sleep(self._backoff)
                self._backoff = min(self._backoff * 2, 30)

    async def _stream(self, url: str, sub: str):
        async with websockets.connect(url, ping_interval=None, close_timeout=5) as ws:
            await ws.send(sub)
            last_ping = time.time()
            async for raw in ws:
                if not self._running:
                    return
                if raw == "pong":
                    continue
                if time.time() - last_ping > 25:
                    await ws.send("ping")
                    last_ping = time.time()
                try:
                    self._process(json.loads(raw))
                except Exception:
                    pass

    def _process(self, msg: dict):
        if "event" in msg:
            if msg.get("event") == "error":
                state.add_log("ERROR", f"OKX WS error: {msg.get('msg', '')}")
            return

        ch   = msg.get("arg", {}).get("channel", "")
        data = msg.get("data", [])
        if not data:
            return

        if ch.startswith("candle"):
            # [ts_ms, open, high, low, close, vol, volCcy, volCcyQuote, confirm]
            for row in data:
                state.update_candle(Candle(
                    time=int(row[0]) // 1000,
                    open=float(row[1]),
                    high=float(row[2]),
                    low=float(row[3]),
                    close=float(row[4]),
                    volume=float(row[5]),
                    is_closed=(len(row) > 8 and row[8] == "1"),
                ))

        elif ch == "tickers":
            d        = data[0]
            price    = float(d.get("last", 0) or 0)
            open_24h = float(d.get("open24h", price) or price)
            chg_pct  = ((price - open_24h) / open_24h * 100) if open_24h else 0.0
            with state.acquire():
                state.ticker["price"]            = price
                state.ticker["bid"]              = float(d.get("bidPx", 0) or 0)
                state.ticker["ask"]              = float(d.get("askPx", 0) or 0)
                state.ticker["high_24h"]         = float(d.get("high24h", 0) or 0)
                state.ticker["low_24h"]          = float(d.get("low24h", 0) or 0)
                state.ticker["volume_24h"]       = float(d.get("volCcy24h", 0) or 0)
                state.ticker["price_change_pct"] = round(chg_pct, 4)
                state.ticker["last_update"]      = time.time()

        elif ch == "books5":
            d = data[0]
            with state.acquire():
                state.orderbook["bids"] = [
                    [float(b[0]), float(b[1])] for b in d.get("bids", [])
                ]
                state.orderbook["asks"] = [
                    [float(a[0]), float(a[1])] for a in d.get("asks", [])
                ]


feed = OKXDataFeed()
