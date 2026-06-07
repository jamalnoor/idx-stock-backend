"""
Yahoo Finance Service
Semua operasi fetch data saham IDX via yfinance
"""

import asyncio
import yfinance as yf
import pandas as pd
import ta
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Mapping nama perusahaan IDX (tambah sesuai kebutuhan)
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
    "UNVR": "Consumer", "ICBP": "Consumer", "INDF": "Consumer", "SIDO": "Consumer", "KLBF": "Farmasi",
    "BREN": "Energi", "MIDI": "Ritel",
}


class YahooFinanceService:

    def _symbol(self, ticker: str) -> str:
        """Konversi kode IDX ke format Yahoo Finance"""
        return f"{ticker}.JK"

    async def fetch_stock(self, ticker: str) -> dict:
        """Fetch data saham lengkap: harga + indikator teknikal"""
        return await asyncio.to_thread(self._fetch_stock_sync, ticker)

    def _fetch_stock_sync(self, ticker: str) -> dict:
        symbol = self._symbol(ticker)
        try:
            tk = yf.Ticker(symbol)
            info = tk.info
            hist = tk.history(period="6mo", interval="1d")

            if hist.empty:
                return {"error": f"Data {ticker} tidak ditemukan di Yahoo Finance"}

            close = hist["Close"]
            high = hist["High"]
            low = hist["Low"]
            volume = hist["Volume"]

            last_price = float(close.iloc[-1])
            prev_price = float(close.iloc[-2]) if len(close) > 1 else last_price
            change = last_price - prev_price
            change_pct = (change / prev_price * 100) if prev_price else 0

            # ── Indikator Teknikal ─────────────────────────────────────
            rsi = float(ta.momentum.RSIIndicator(close, window=14).rsi().iloc[-1])

            macd_ind = ta.trend.MACD(close)
            macd_val = float(macd_ind.macd().iloc[-1])
            macd_sig = float(macd_ind.macd_signal().iloc[-1])
            macd_hist = float(macd_ind.macd_diff().iloc[-1])

            bb = ta.volatility.BollingerBands(close)
            bb_upper = float(bb.bollinger_hband().iloc[-1])
            bb_lower = float(bb.bollinger_lband().iloc[-1])
            bb_mid = float(bb.bollinger_mavg().iloc[-1])

            stoch = ta.momentum.StochasticOscillator(high, low, close)
            stoch_k = float(stoch.stoch().iloc[-1])
            stoch_d = float(stoch.stoch_signal().iloc[-1])

            adx_ind = ta.trend.ADXIndicator(high, low, close)
            adx = float(adx_ind.adx().iloc[-1])
            adx_pos = float(adx_ind.adx_pos().iloc[-1])
            adx_neg = float(adx_ind.adx_neg().iloc[-1])

            cci = float(ta.trend.CCIIndicator(high, low, close).cci().iloc[-1])
            atr = float(ta.volatility.AverageTrueRange(high, low, close).average_true_range().iloc[-1])

            ma20 = float(close.rolling(20).mean().iloc[-1])
            ma50 = float(close.rolling(50).mean().iloc[-1])
            ma200 = float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else None

            # ── Volume ─────────────────────────────────────────────────
            vol_today = int(volume.iloc[-1])
            vol_avg20 = float(volume.rolling(20).mean().iloc[-1])
            vol_ratio = vol_today / vol_avg20 if vol_avg20 > 0 else 1

            # ── BB Position ────────────────────────────────────────────
            if last_price >= bb_upper:
                bb_pos = "Upper"
            elif last_price <= bb_lower:
                bb_pos = "Lower"
            else:
                bb_pct = (last_price - bb_lower) / (bb_upper - bb_lower) * 100 if (bb_upper - bb_lower) > 0 else 50
                bb_pos = f"Middle ({bb_pct:.0f}%)"

            # ── Fundamental dari info ─────────────────────────────────
            pe = info.get("trailingPE") or info.get("forwardPE") or 0
            roe = (info.get("returnOnEquity") or 0) * 100
            mkt_cap = info.get("marketCap") or 0
            avg_vol = info.get("averageVolume") or vol_avg20

            return {
                "ticker": ticker,
                "name": IDX_NAMES.get(ticker, info.get("longName", ticker)),
                "sector": IDX_SECTORS.get(ticker, info.get("sector", "—")),
                "price": round(last_price, 2),
                "change": round(change, 2),
                "change_pct": round(change_pct, 2),
                "volume": vol_today,
                "volume_avg": int(vol_avg20),
                "volume_ratio": round(vol_ratio, 2),
                "fundamentals": {
                    "pe": round(pe, 2) if pe else None,
                    "roe": round(roe, 2) if roe else None,
                    "market_cap": mkt_cap,
                    "currency": info.get("currency", "IDR"),
                },
                "indicators": {
                    "rsi": round(rsi, 2),
                    "macd": round(macd_val, 4),
                    "macd_signal": round(macd_sig, 4),
                    "macd_hist": round(macd_hist, 4),
                    "bb_position": bb_pos,
                    "bb_upper": round(bb_upper, 2),
                    "bb_lower": round(bb_lower, 2),
                    "bb_mid": round(bb_mid, 2),
                    "stoch_k": round(stoch_k, 2),
                    "stoch_d": round(stoch_d, 2),
                    "adx": round(adx, 2),
                    "adx_pos": round(adx_pos, 2),
                    "adx_neg": round(adx_neg, 2),
                    "cci": round(cci, 2),
                    "atr": round(atr, 2),
                    "ma20": round(ma20, 2),
                    "ma50": round(ma50, 2),
                    "ma200": round(ma200, 2) if ma200 else None,
                    "price_vs_ma20": round((last_price / ma20 - 1) * 100, 2) if ma20 else 0,
                    "price_vs_ma50": round((last_price / ma50 - 1) * 100, 2) if ma50 else 0,
                },
                "risk": {
                    "stop_loss": round(last_price - 2 * atr, 2),
                    "target_1": round(last_price + 2 * atr, 2),
                    "target_2": round(last_price + 4 * atr, 2),
                    "atr_pct": round(atr / last_price * 100, 2),
                },
            }

        except Exception as e:
            logger.error(f"Error fetching {ticker}: {e}")
            return {"error": str(e), "ticker": ticker}

    async def fetch_history(self, ticker: str, period: str = "1mo", interval: str = "1d") -> dict:
        """Fetch data historis OHLCV untuk candlestick chart"""
        return await asyncio.to_thread(self._fetch_history_sync, ticker, period, interval)

    def _fetch_history_sync(self, ticker: str, period: str, interval: str) -> dict:
        symbol = self._symbol(ticker)
        try:
            tk = yf.Ticker(symbol)
            hist = tk.history(period=period, interval=interval)

            if hist.empty:
                return {"error": f"History {ticker} tidak ditemukan"}

            candles = []
            for ts, row in hist.iterrows():
                candles.append({
                    "t": ts.isoformat(),
                    "o": round(float(row["Open"]), 2),
                    "h": round(float(row["High"]), 2),
                    "l": round(float(row["Low"]), 2),
                    "c": round(float(row["Close"]), 2),
                    "v": int(row["Volume"]),
                })

            return {"ticker": ticker, "period": period, "interval": interval, "candles": candles}

        except Exception as e:
            return {"error": str(e)}

    async def fetch_foreign_flow(self, ticker: str) -> dict:
        """
        Estimasi net foreign flow dari perubahan harga dan volume.
        Data asing sesungguhnya hanya tersedia dari IDX resmi.
        """
        data = await self.fetch_stock(ticker)
        if "error" in data:
            return data

        price = data["price"]
        vol = data["volume"]
        vol_ratio = data.get("volume_ratio", 1)
        change_pct = data["change_pct"]

        # Estimasi sederhana: volume besar + naik = kemungkinan akumulasi asing
        estimated_net = round(price * vol * (change_pct / 100) * 0.3 / 1_000_000, 2)

        return {
            "ticker": ticker,
            "estimated_net_foreign_m": estimated_net,
            "flow_type": "Accumulation" if estimated_net > 0 else "Distribution",
            "volume_ratio": vol_ratio,
            "note": "Estimasi dari volume & perubahan harga. Data asing resmi: idx.co.id",
        }
