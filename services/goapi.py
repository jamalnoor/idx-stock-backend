"""
GoAPI IDX Service
Pengganti YahooFinanceService - menggunakan GOAPI.io untuk data saham IDX real
Dokumentasi: https://goapi.io/docs/
"""
import asyncio
import aiohttp
import os
import ta
import pandas as pd
import logging
from typing import Optional

logger = logging.getLogger(__name__)

GOAPI_KEY = os.getenv("GOAPI_KEY", "")
GOAPI_BASE = "https://app.goapi.io"

IDX_NAMES = {
    "BBCA": "Bank Central Asia Tbk",
    "BBRI": "Bank Rakyat Indonesia Tbk",
    "BMRI": "Bank Mandiri Tbk",
    "BBNI": "Bank Negara Indonesia Tbk",
    "TLKM": "Telkom Indonesia Tbk",
    "ASII": "Astra International Tbk",
    "UNVR": "Unilever Indonesia Tbk",
    "ICBP": "Indofood CBP Sukses Makmur Tbk",
    "INDF": "Indofood Sukses Makmur Tbk",
    "GOTO": "GoTo Gojek Tokopedia Tbk",
    "BREN": "Barito Renewables Energy Tbk",
    "MIDI": "Midi Utama Indonesia Tbk",
    "MAPI": "Mitra Adiperkasa Tbk",
    "SIDO": "Industri Jamu Sido Muncul Tbk",
    "KLBF": "Kalbe Farma Tbk",
}

IDX_SECTORS = {
    "BBCA": "Perbankan", "BBRI": "Perbankan", "BMRI": "Perbankan", "BBNI": "Perbankan",
    "TLKM": "Telekomunikasi", "GOTO": "Teknologi",
    "ASII": "Otomotif", "MAPI": "Ritel",
    "UNVR": "Consumer", "ICBP": "Consumer", "INDF": "Consumer",
    "SIDO": "Consumer", "KLBF": "Farmasi",
    "BREN": "Energi", "MIDI": "Ritel",
}

# Map period ke parameter GOAPI
PERIOD_MAP = {
    "1wk":  {"range": "7",   "interval": "D"},
    "1mo":  {"range": "30",  "interval": "D"},
    "3mo":  {"range": "90",  "interval": "D"},
    "6mo":  {"range": "180", "interval": "D"},
    "1y":   {"range": "365", "interval": "D"},
}

INTERVAL_MAP = {
    "15m": "15",
    "1h":  "60",
    "1d":  "D",
    "1wk": "W",
}


class GoAPIService:
    """Servis data saham IDX via GOAPI.io — drop-in pengganti YahooFinanceService"""

    def __init__(self):
        if not GOAPI_KEY:
            logger.warning("GOAPI_KEY tidak ditemukan! Set environment variable GOAPI_KEY.")

    # ─── INTERNAL HELPERS ──────────────────────────────────────────────────

    async def _get(self, path: str, params: dict = {}) -> dict:
        """HTTP GET ke GOAPI dengan API key"""
        params["api_key"] = GOAPI_KEY
        url = f"{GOAPI_BASE}{path}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status == 401:
                        return {"error": "API key tidak valid. Cek GOAPI_KEY kamu."}
                    if resp.status == 429:
                        return {"error": "Rate limit GOAPI tercapai. Coba beberapa saat lagi."}
                    if resp.status != 200:
                        return {"error": f"GOAPI error HTTP {resp.status}"}
                    return await resp.json()
        except asyncio.TimeoutError:
            return {"error": "Timeout saat menghubungi GOAPI"}
        except Exception as e:
            logger.error(f"GoAPI request error: {e}")
            return {"error": str(e)}

    def _calc_indicators(self, df: pd.DataFrame) -> dict:
        """Hitung indikator teknikal dari DataFrame OHLCV"""
        close  = df["close"]
        high   = df["high"]
        low    = df["low"]
        volume = df["volume"]

        last_price = float(close.iloc[-1])
        prev_price = float(close.iloc[-2]) if len(close) > 1 else last_price

        rsi = float(ta.momentum.RSIIndicator(close, window=14).rsi().iloc[-1])

        macd_ind  = ta.trend.MACD(close)
        macd_val  = float(macd_ind.macd().iloc[-1])
        macd_sig  = float(macd_ind.macd_signal().iloc[-1])
        macd_hist = float(macd_ind.macd_diff().iloc[-1])

        bb        = ta.volatility.BollingerBands(close)
        bb_upper  = float(bb.bollinger_hband().iloc[-1])
        bb_lower  = float(bb.bollinger_lband().iloc[-1])
        bb_mid    = float(bb.bollinger_mavg().iloc[-1])

        stoch   = ta.momentum.StochasticOscillator(high, low, close)
        stoch_k = float(stoch.stoch().iloc[-1])
        stoch_d = float(stoch.stoch_signal().iloc[-1])

        adx_ind = ta.trend.ADXIndicator(high, low, close)
        adx     = float(adx_ind.adx().iloc[-1])
        adx_pos = float(adx_ind.adx_pos().iloc[-1])
        adx_neg = float(adx_ind.adx_neg().iloc[-1])

        cci = float(ta.trend.CCIIndicator(high, low, close).cci().iloc[-1])
        atr = float(ta.volatility.AverageTrueRange(high, low, close).average_true_range().iloc[-1])

        ma20  = float(close.rolling(20).mean().iloc[-1])
        ma50  = float(close.rolling(50).mean().iloc[-1])
        ma200 = float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else None

        vol_today  = int(volume.iloc[-1])
        vol_avg20  = float(volume.rolling(20).mean().iloc[-1])
        vol_ratio  = vol_today / vol_avg20 if vol_avg20 > 0 else 1

        # BB position label
        if last_price >= bb_upper:
            bb_pos = "Upper"
        elif last_price <= bb_lower:
            bb_pos = "Lower"
        else:
            pct = (last_price - bb_lower) / (bb_upper - bb_lower) * 100 if (bb_upper - bb_lower) > 0 else 50
            bb_pos = f"Middle ({pct:.0f}%)"

        return {
            "last_price": last_price,
            "prev_price": prev_price,
            "vol_today":  vol_today,
            "vol_avg20":  vol_avg20,
            "vol_ratio":  round(vol_ratio, 2),
            "atr": round(atr, 2),
            "indicators": {
                "rsi":          round(rsi, 2),
                "macd":         round(macd_val, 4),
                "macd_signal":  round(macd_sig, 4),
                "macd_hist":    round(macd_hist, 4),
                "bb_position":  bb_pos,
                "bb_upper":     round(bb_upper, 2),
                "bb_lower":     round(bb_lower, 2),
                "bb_mid":       round(bb_mid, 2),
                "stoch_k":      round(stoch_k, 2),
                "stoch_d":      round(stoch_d, 2),
                "adx":          round(adx, 2),
                "adx_pos":      round(adx_pos, 2),
                "adx_neg":      round(adx_neg, 2),
                "cci":          round(cci, 2),
                "atr":          round(atr, 2),
                "ma20":         round(ma20, 2),
                "ma50":         round(ma50, 2),
                "ma200":        round(ma200, 2) if ma200 else None,
                "price_vs_ma20": round((last_price / ma20 - 1) * 100, 2) if ma20 else 0,
                "price_vs_ma50": round((last_price / ma50 - 1) * 100, 2) if ma50 else 0,
            },
        }

    # ─── PUBLIC API (same interface as YahooFinanceService) ───────────────

    async def fetch_stock(self, ticker: str) -> dict:
        """
        Fetch data saham lengkap: harga real + indikator teknikal.
        Output identik dengan YahooFinanceService.fetch_stock()
        """
        # 1. Snapshot harga real-time
        snap = await self._get(f"/stock/idx/{ticker}")
        if "error" in snap:
            return {"error": snap["error"], "ticker": ticker}

        # 2. Data historis 6 bulan untuk hitung indikator
        hist = await self._get(f"/stock/idx/{ticker}/history", {
            "range": "180", "interval": "D"
        })
        if "error" in hist or not hist.get("data"):
            return {"error": f"Gagal ambil history {ticker}", "ticker": ticker}

        try:
            df = pd.DataFrame(hist["data"])
            df.columns = [c.lower() for c in df.columns]
            df = df[["open", "high", "low", "close", "volume"]].astype(float)
            df = df.dropna().reset_index(drop=True)

            if len(df) < 26:
                return {"error": f"Data historis {ticker} tidak cukup untuk indikator", "ticker": ticker}

            ind = self._calc_indicators(df)

            last_price = float(snap.get("last_price") or snap.get("close") or ind["last_price"])
            prev_price = ind["prev_price"]
            change     = round(last_price - prev_price, 2)
            change_pct = round((change / prev_price * 100) if prev_price else 0, 2)
            atr        = ind["atr"]

            return {
                "ticker":       ticker,
                "name":         IDX_NAMES.get(ticker, snap.get("name", ticker)),
                "sector":       IDX_SECTORS.get(ticker, "—"),
                "price":        round(last_price, 2),
                "change":       change,
                "change_pct":   change_pct,
                "volume":       ind["vol_today"],
                "volume_avg":   int(ind["vol_avg20"]),
                "volume_ratio": ind["vol_ratio"],
                "fundamentals": {
                    "pe":         snap.get("pe_ratio") or snap.get("pe"),
                    "roe":        snap.get("roe"),
                    "market_cap": snap.get("market_cap") or snap.get("mkt_cap"),
                    "currency":   "IDR",
                },
                "indicators": ind["indicators"],
                "risk": {
                    "stop_loss": round(last_price - 2 * atr, 2),
                    "target_1":  round(last_price + 2 * atr, 2),
                    "target_2":  round(last_price + 4 * atr, 2),
                    "atr_pct":   round(atr / last_price * 100, 2) if last_price else 0,
                },
            }

        except Exception as e:
            logger.error(f"Error processing {ticker}: {e}")
            return {"error": str(e), "ticker": ticker}

    async def fetch_history(self, ticker: str, period: str = "1mo", interval: str = "1d") -> dict:
        """
        Fetch data historis OHLCV untuk candlestick chart.
        Output identik dengan YahooFinanceService.fetch_history()
        """
        p = PERIOD_MAP.get(period, {"range": "30", "interval": "D"})
        iv = INTERVAL_MAP.get(interval, "D")

        raw = await self._get(f"/stock/idx/{ticker}/history", {
            "range": p["range"], "interval": iv
        })

        if "error" in raw or not raw.get("data"):
            return {"error": f"History {ticker} tidak ditemukan", "ticker": ticker}

        try:
            candles = []
            for row in raw["data"]:
                candles.append({
                    "t": row.get("date") or row.get("datetime") or row.get("t"),
                    "o": round(float(row.get("open",  0)), 2),
                    "h": round(float(row.get("high",  0)), 2),
                    "l": round(float(row.get("low",   0)), 2),
                    "c": round(float(row.get("close", 0)), 2),
                    "v": int(float(row.get("volume", 0))),
                })
            return {"ticker": ticker, "period": period, "interval": interval, "candles": candles}
        except Exception as e:
            return {"error": str(e), "ticker": ticker}

    async def fetch_foreign_flow(self, ticker: str) -> dict:
        """
        Net foreign flow dari GOAPI (jika tersedia) atau estimasi.
        """
        raw = await self._get(f"/stock/idx/{ticker}/foreign")

        # Kalau GOAPI punya endpoint foreign flow
        if "error" not in raw and raw.get("data"):
            d = raw["data"]
            return {
                "ticker":               ticker,
                "net_foreign_buy_m":    d.get("net_foreign_buy"),
                "net_foreign_sell_m":   d.get("net_foreign_sell"),
                "flow_type":            "Accumulation" if (d.get("net_foreign_buy") or 0) > 0 else "Distribution",
                "source":               "GOAPI real data",
            }

        # Fallback: estimasi dari data harga
        data = await self.fetch_stock(ticker)
        if "error" in data:
            return data

        price      = data["price"]
        vol        = data["volume"]
        vol_ratio  = data.get("volume_ratio", 1)
        change_pct = data["change_pct"]
        estimated  = round(price * vol * (change_pct / 100) * 0.3 / 1_000_000, 2)

        return {
            "ticker":                  ticker,
            "estimated_net_foreign_m": estimated,
            "flow_type":               "Accumulation" if estimated > 0 else "Distribution",
            "volume_ratio":            vol_ratio,
            "note":                    "Estimasi dari volume & perubahan harga. Data asing resmi: idx.co.id",
        }
