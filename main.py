"""
IDX Stock Dashboard - Backend API
Deploy ke Railway: https://railway.app
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
import json
import os
import logging
from datetime import datetime

from services.yahoo import YahooFinanceService
from services.cache import CacheService
from services.signals import SignalEngine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting IDX Stock API...")
    yield
    logger.info("Shutting down...")


app = FastAPI(
    title="IDX Stock Dashboard API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Ganti dengan domain Vercel kamu di production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

yahoo = YahooFinanceService()
cache = CacheService()
engine = SignalEngine()

# ─── REST ENDPOINTS ───────────────────────────────────────────

@app.get("/")
def root():
    return {"status": "ok", "message": "IDX Stock API running"}


@app.get("/api/stock/{ticker}")
async def get_stock(ticker: str):
    """Ambil data 1 saham lengkap dengan indikator teknikal & sinyal"""
    ticker = ticker.upper().strip()
    cached = cache.get(f"stock:{ticker}")
    if cached:
        return cached

    data = await yahoo.fetch_stock(ticker)
    if "error" in data:
        raise HTTPException(status_code=404, detail=data["error"])

    data["signal"] = engine.analyze(data["indicators"])
    cache.set(f"stock:{ticker}", data, ttl=300)  # Cache 5 menit
    return data


@app.get("/api/stocks")
async def get_multiple_stocks(
    tickers: str = Query(default="BBCA,BBRI,TLKM,ASII,UNVR,GOTO,BREN,MIDI")
):
    """Ambil banyak saham sekaligus (untuk watchlist)"""
    ticker_list = [t.strip().upper() for t in tickers.split(",")][:20]
    tasks = [yahoo.fetch_stock(t) for t in ticker_list]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    output = {}
    for ticker, result in zip(ticker_list, results):
        if isinstance(result, Exception):
            output[ticker] = {"error": str(result)}
        else:
            result["signal"] = engine.analyze(result.get("indicators", {}))
            output[ticker] = result

    return output


@app.get("/api/history/{ticker}")
async def get_history(
    ticker: str,
    period: str = Query(default="1mo", enum=["1wk", "1mo", "3mo", "6mo", "1y"]),
    interval: str = Query(default="1d", enum=["15m", "1h", "1d", "1wk"]),
):
    """Ambil data historis OHLCV untuk charting"""
    ticker = ticker.upper().strip()
    cache_key = f"history:{ticker}:{period}:{interval}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    data = await yahoo.fetch_history(ticker, period=period, interval=interval)
    if "error" in data:
        raise HTTPException(status_code=404, detail=data["error"])

    cache.set(cache_key, data, ttl=60 if interval in ["15m", "1h"] else 300)
    return data


@app.get("/api/screener")
async def screener(
    min_rsi: float = Query(default=30),
    max_rsi: float = Query(default=70),
    min_score: float = Query(default=6.0),
    sector: str = Query(default="all"),
):
    """Filter saham berdasarkan kriteria teknikal"""
    watchlist = "BBCA,BBRI,BMRI,BBNI,TLKM,ASII,UNVR,ICBP,INDF,GOTO,BREN,MIDI,MAPI,SIDO,KLBF"
    tickers = [t.strip() for t in watchlist.split(",")]

    tasks = [yahoo.fetch_stock(t) for t in tickers]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    filtered = []
    for ticker, result in zip(tickers, results):
        if isinstance(result, Exception):
            continue
        inds = result.get("indicators", {})
        rsi = inds.get("rsi", 50)
        signal = engine.analyze(inds)
        score = signal.get("score", 5)

        if min_rsi <= rsi <= max_rsi and score >= min_score:
            result["signal"] = signal
            filtered.append(result)

    filtered.sort(key=lambda x: x["signal"]["score"], reverse=True)
    return {"results": filtered, "count": len(filtered)}


@app.get("/api/foreign/{ticker}")
async def get_foreign_flow(ticker: str):
    """Data net foreign flow (beli/jual asing)"""
    ticker = ticker.upper().strip()
    data = await yahoo.fetch_foreign_flow(ticker)
    return data


# ─── WEBSOCKET REALTIME ───────────────────────────────────────

class ConnectionManager:
    def __init__(self):
        self.active: dict[str, list[WebSocket]] = {}

    async def connect(self, ws: WebSocket, ticker: str):
        await ws.accept()
        self.active.setdefault(ticker, []).append(ws)
        logger.info(f"WS connected: {ticker} ({len(self.active[ticker])} clients)")

    def disconnect(self, ws: WebSocket, ticker: str):
        if ticker in self.active:
            self.active[ticker] = [c for c in self.active[ticker] if c != ws]

    async def broadcast(self, ticker: str, data: dict):
        clients = self.active.get(ticker, [])
        dead = []
        for ws in clients:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws, ticker)


manager = ConnectionManager()


@app.websocket("/ws/{ticker}")
async def ws_stock(websocket: WebSocket, ticker: str):
    ticker = ticker.upper().strip()
    await manager.connect(websocket, ticker)
    try:
        while True:
            data = await yahoo.fetch_stock(ticker)
            if "error" not in data:
                data["signal"] = engine.analyze(data["indicators"])
                data["timestamp"] = datetime.utcnow().isoformat()
            await websocket.send_json(data)
            await asyncio.sleep(30)  # Update tiap 30 detik
    except WebSocketDisconnect:
        manager.disconnect(websocket, ticker)
        logger.info(f"WS disconnected: {ticker}")
