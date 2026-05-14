# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install deps and run locally
pip install -r requirements.txt
streamlit run app.py

# Windows one-liner
run.bat

# Docker
docker compose up --build
```

Dashboard opens at `http://localhost:8501`.

## Architecture

### Thread model

Four daemon threads run alongside Streamlit's main thread. All share a single `SharedState` instance (`backend/shared_state.py`) protected by an `RLock`. Always acquire via `with state.acquire():`.

| Thread | File | Responsibility |
|--------|------|----------------|
| `BinanceFeed` | `backend/data_feed.py` | asyncio loop → Binance public WebSocket (kline, bookTicker, miniTicker, depth5). No API key needed. |
| `StrategyEngine` | `backend/strategy_engine.py` | Computes RSI, MACD, Bollinger Band, Volume Profile, Order Flow signals every second. Updates `state.strategies` and `state.ensemble_signal`. |
| `RiskEngine` | `backend/risk_engine.py` | Updates unrealized P&L, max drawdown, performance metrics every second. Fires circuit breakers. |
| `OrderManager` | `backend/order_manager.py` | Paper-trading only. Simulates fills with randomized slippage in a sub-thread per order. |

Threads start once via a `st.session_state.backend_started` guard in `app.py`.

### Streamlit refresh pattern

`app.py` runs a `while True: time.sleep(1)` loop inside `st.empty().container()`. The sidebar renders outside the loop; widget changes trigger Streamlit's normal script rerun, which restarts the loop with new values. This means **sidebar state is read once at the top of each loop iteration** — changes take effect on the next rerun, not mid-loop.

### Data flow

```
Binance WS ──► BinanceFeed ──► state.candles / ticker / orderbook
state.candles ──► StrategyEngine ──► state.strategies / ensemble_signal / confluence_met
state ──► RiskEngine ──► state.position.unrealized_pnl / max_drawdown / performance / circuit_breakers
Streamlit loop reads state ──► renders UI (1 s cadence)
```

### Circuit breakers

Defined in `SharedState.check_circuit_breakers()`, called by `RiskEngine` each tick:
- **daily_loss_triggered**: `daily_pnl <= -daily_loss_limit` (default $500)
- **mdd_triggered**: `max_drawdown >= 20%`
- **manual_stop**: set by `OrderManager.emergency_stop()`

All three set `state.trading_active = False`. Reset from the sidebar "Reset Breakers" button.

### Logging

`backend/logger.py` writes every event to `logs/omni_YYYYMMDD_HHMMSS.jsonl` (one JSON object per line). It also calls `state.add_log()` which feeds the in-dashboard log tail (deque, maxlen 50).

### Extending strategies

Add a new method `_yourname_signal(self, closes, ...) -> tuple[int, float]` in `StrategyEngine`, then add its key to `SharedState.strategies` in `shared_state.py`. The ensemble consensus picks it up automatically.

### Connecting to a live broker

`OrderManager._simulate_fill()` is the paper-trading stub. Replace it with real exchange API calls (e.g., CCXT `create_order()`). The rest of the state machine (position tracking, circuit breakers, P&L) remains unchanged.
