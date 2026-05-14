import threading
import time

import numpy as np

from .shared_state import state


class StrategyEngine:
    def __init__(self):
        self._thread: threading.Thread = None
        self._running = False

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="StrategyEngine"
        )
        self._thread.start()

    def stop(self):
        self._running = False

    # ── Main loop ─────────────────────────────────────────────────────────

    def _run(self):
        while self._running:
            candles = state.get_candles()
            if len(candles) >= 20:
                self._compute(candles)
            time.sleep(1)

    def _compute(self, candles):
        closes  = np.array([c.close  for c in candles], dtype=float)
        volumes = np.array([c.volume for c in candles], dtype=float)

        results = {
            "RSI Momentum":      self._rsi_signal(closes),
            "MACD Cross":        self._macd_signal(closes),
            "BB Squeeze":        self._bb_signal(closes),
            "Volume Profile":    self._volume_signal(closes, volumes),
            "Order Flow Imbal.": self._flow_signal(closes, volumes),
        }

        with state.acquire():
            active = []
            for name, strat in state.strategies.items():
                if not strat["enabled"]:
                    continue
                sig, prob = results.get(name, (0, 0.5))
                strat["signal"]   = sig
                strat["win_prob"] = round(prob, 3)
                if sig != 0:
                    active.append(sig)

            consensus = sum(active)
            state.ensemble_signal = (
                1 if consensus > 0 else (-1 if consensus < 0 else 0)
            )
            state.confluence_met = abs(consensus) >= 3

    # ── Individual strategies ─────────────────────────────────────────────

    def _rsi_signal(self, closes, period=14):
        rsi = self._rsi(closes, period)
        if rsi < 30:
            return (1,  min(0.5 + (30 - rsi) / 50, 0.88))
        if rsi > 70:
            return (-1, min(0.5 + (rsi - 70) / 50, 0.88))
        return (0, 0.5)

    def _macd_signal(self, closes):
        if len(closes) < 27:
            return (0, 0.5)
        ema12 = self._ema(closes, 12)
        ema26 = self._ema(closes, 26)
        macd  = ema12 - ema26

        prev12 = self._ema(closes[:-1], 12)
        prev26 = self._ema(closes[:-1], 26)
        prev_macd = prev12 - prev26

        if macd > prev_macd and macd > 0:
            return (1,  0.63)
        if macd < prev_macd and macd < 0:
            return (-1, 0.62)
        if macd > prev_macd:
            return (1,  0.54)
        if macd < prev_macd:
            return (-1, 0.54)
        return (0, 0.5)

    def _bb_signal(self, closes, period=20):
        if len(closes) < period:
            return (0, 0.5)
        recent = closes[-period:]
        mid    = np.mean(recent)
        std    = np.std(recent)
        upper  = mid + 2 * std
        lower  = mid - 2 * std
        price  = closes[-1]

        hist_std = np.std(closes[-50:]) if len(closes) >= 50 else std
        squeeze  = std < hist_std * 0.75

        if squeeze and price > mid:
            return (1,  0.72)
        if squeeze and price < mid:
            return (-1, 0.71)
        if price > upper:
            return (-1, 0.64)
        if price < lower:
            return (1,  0.65)
        return (0, 0.5)

    def _volume_signal(self, closes, volumes):
        if len(closes) < 10:
            return (0, 0.5)
        avg_vol    = np.mean(volumes[-20:]) if len(volumes) >= 20 else np.mean(volumes)
        recent_vol = np.mean(volumes[-5:])
        trend      = closes[-1] - closes[-5]

        if recent_vol > avg_vol * 1.4 and trend > 0:
            return (1,  0.66)
        if recent_vol > avg_vol * 1.4 and trend < 0:
            return (-1, 0.66)
        return (0, 0.5)

    def _flow_signal(self, closes, volumes):
        if len(closes) < 5:
            return (0, 0.5)
        chg      = (closes[-1] - closes[-5]) / closes[-5] if closes[-5] else 0
        avg_vol  = np.mean(volumes[-10:]) if len(volumes) >= 10 else np.mean(volumes)
        surge    = volumes[-1] > avg_vol * 1.5

        if surge and chg > 0.001:
            return (1,  0.69)
        if surge and chg < -0.001:
            return (-1, 0.68)
        return (0, 0.5)

    # ── Indicators ────────────────────────────────────────────────────────

    @staticmethod
    def _rsi(prices, period=14):
        if len(prices) < period + 1:
            return 50.0
        deltas = np.diff(prices)
        gains  = np.where(deltas > 0, deltas, 0.0)
        losses = np.where(deltas < 0, -deltas, 0.0)
        avg_g  = np.mean(gains[-period:])
        avg_l  = np.mean(losses[-period:])
        if avg_l == 0:
            return 100.0
        return 100 - (100 / (1 + avg_g / avg_l))

    @staticmethod
    def _ema(prices, period):
        if len(prices) == 0:
            return 0.0
        alpha = 2 / (period + 1)
        val   = float(prices[0])
        for p in prices[1:]:
            val = alpha * float(p) + (1 - alpha) * val
        return val


engine = StrategyEngine()
