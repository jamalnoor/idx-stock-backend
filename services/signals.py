"""
Signal Engine - Mesin Analisis Sinyal Saham
Menghasilkan rekomendasi BUY/HOLD/SELL berdasarkan indikator teknikal
"""

from typing import Optional


class SignalEngine:
    """
    Sistem scoring multi-indikator untuk menghasilkan sinyal trading.
    Setiap indikator berkontribusi ke skor 0–10.
    """

    def analyze(self, indicators: dict) -> dict:
        if not indicators:
            return {"action": "N/A", "score": 5.0, "reasons": []}

        score = 5.0
        reasons = []
        signals = {}

        # ── RSI (bobot: 2 poin) ───────────────────────────────────────
        rsi = indicators.get("rsi", 50)
        if rsi < 30:
            score += 2.0
            reasons.append(f"RSI {rsi:.0f} — Oversold, potensi reversal naik")
            signals["rsi"] = "OVERSOLD_BULLISH"
        elif rsi < 40:
            score += 1.0
            reasons.append(f"RSI {rsi:.0f} — Mendekati oversold")
            signals["rsi"] = "APPROACHING_OVERSOLD"
        elif rsi > 70:
            score -= 2.0
            reasons.append(f"RSI {rsi:.0f} — Overbought, waspadai koreksi")
            signals["rsi"] = "OVERBOUGHT_BEARISH"
        elif rsi > 60:
            score -= 0.5
            reasons.append(f"RSI {rsi:.0f} — Mendekati overbought")
            signals["rsi"] = "APPROACHING_OVERBOUGHT"
        else:
            reasons.append(f"RSI {rsi:.0f} — Netral")
            signals["rsi"] = "NEUTRAL"

        # ── MACD (bobot: 2 poin) ──────────────────────────────────────
        macd = indicators.get("macd", 0)
        macd_sig = indicators.get("macd_signal", 0)
        macd_hist = indicators.get("macd_hist", 0)
        if macd > macd_sig and macd_hist > 0:
            score += 2.0
            reasons.append("MACD di atas signal line — momentum bullish")
            signals["macd"] = "BULLISH_CROSSOVER"
        elif macd > macd_sig:
            score += 1.0
            reasons.append("MACD baru crossover bullish")
            signals["macd"] = "BULLISH"
        elif macd < macd_sig and macd_hist < 0:
            score -= 2.0
            reasons.append("MACD di bawah signal line — momentum bearish")
            signals["macd"] = "BEARISH_CROSSOVER"
        else:
            score -= 0.5
            signals["macd"] = "BEARISH"

        # ── Moving Average (bobot: 2 poin) ────────────────────────────
        price = indicators.get("price_vs_ma20", 0)
        p_vs_ma50 = indicators.get("price_vs_ma50", 0)
        ma20 = indicators.get("ma20", 0)
        ma50 = indicators.get("ma50", 0)
        if price > 0 and p_vs_ma50 > 0:
            score += 2.0
            reasons.append(f"Harga di atas MA20 & MA50 — tren naik terkonfirmasi")
            signals["ma"] = "ABOVE_BOTH_MA"
        elif price > 0:
            score += 0.5
            reasons.append("Harga di atas MA20, mendekati MA50")
            signals["ma"] = "ABOVE_MA20"
        elif price < 0 and p_vs_ma50 < 0:
            score -= 2.0
            reasons.append("Harga di bawah MA20 & MA50 — tren turun")
            signals["ma"] = "BELOW_BOTH_MA"
        else:
            signals["ma"] = "MIXED"

        # ── Bollinger Bands (bobot: 1 poin) ───────────────────────────
        bb_pos = indicators.get("bb_position", "Middle")
        if "Lower" in str(bb_pos):
            score += 1.0
            reasons.append("Harga di Bollinger Lower — potensi bounce")
            signals["bb"] = "LOWER_BAND_BOUNCE"
        elif "Upper" in str(bb_pos):
            score -= 0.5
            reasons.append("Harga menyentuh Bollinger Upper — hati-hati")
            signals["bb"] = "UPPER_BAND_WARNING"
        else:
            signals["bb"] = "MIDDLE"

        # ── ADX (bobot: 1 poin) ───────────────────────────────────────
        adx = indicators.get("adx", 20)
        adx_pos = indicators.get("adx_pos", 0)
        adx_neg = indicators.get("adx_neg", 0)
        if adx > 25:
            if adx_pos > adx_neg:
                score += 1.0
                reasons.append(f"ADX {adx:.0f} — tren kuat ke atas")
                signals["adx"] = "STRONG_UPTREND"
            else:
                score -= 1.0
                reasons.append(f"ADX {adx:.0f} — tren kuat ke bawah")
                signals["adx"] = "STRONG_DOWNTREND"
        else:
            reasons.append(f"ADX {adx:.0f} — sideways / tren lemah")
            signals["adx"] = "WEAK_TREND"

        # ── Stochastic (bobot: 1 poin) ────────────────────────────────
        stoch = indicators.get("stoch_k", 50)
        if stoch < 20:
            score += 1.0
            reasons.append(f"Stochastic {stoch:.0f} — oversold")
            signals["stoch"] = "OVERSOLD"
        elif stoch > 80:
            score -= 1.0
            reasons.append(f"Stochastic {stoch:.0f} — overbought")
            signals["stoch"] = "OVERBOUGHT"
        else:
            signals["stoch"] = "NEUTRAL"

        # ── CCI (bobot: 1 poin) ───────────────────────────────────────
        cci = indicators.get("cci", 0)
        if cci < -100:
            score += 0.5
            signals["cci"] = "OVERSOLD"
        elif cci > 100:
            score -= 0.5
            signals["cci"] = "OVERBOUGHT"
        else:
            signals["cci"] = "NEUTRAL"

        # Clamp score ke 0–10
        score = round(max(0.0, min(10.0, score)), 1)

        # ── Tentukan action ───────────────────────────────────────────
        if score >= 8.0:
            action = "STRONG BUY"
            desc = "Sinyal beli sangat kuat. Multi-indikator konfirmasi bullish."
        elif score >= 6.5:
            action = "BUY"
            desc = "Sinyal beli. Setup bagus untuk entry."
        elif score >= 5.5:
            action = "HOLD / ACCUMULATE"
            desc = "Netral cenderung positif. Akumulasi bertahap bisa dipertimbangkan."
        elif score >= 4.0:
            action = "HOLD"
            desc = "Sinyal mixed. Tunggu konfirmasi arah."
        elif score >= 2.5:
            action = "CAUTION / REDUCE"
            desc = "Sinyal melemah. Pertimbangkan kurangi posisi."
        else:
            action = "SELL"
            desc = "Sinyal jual. Hindari atau exit posisi."

        return {
            "action": action,
            "score": score,
            "description": desc,
            "reasons": reasons[:4],  # Top 4 alasan
            "signals": signals,
        }
