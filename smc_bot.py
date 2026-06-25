#!/usr/bin/env python3
"""
SMC Signal Bot — Smart Money Concepts
Отправляет сигналы в Telegram
Работает на VPS без компьютера
"""

import time
import requests
from datetime import datetime

# ═══════════════════════════════════════════════
#  НАСТРОЙКИ — ЗАПОЛНИ СВОИМИ ДАННЫМИ
# ═══════════════════════════════════════════════
TELEGRAM_TOKEN  = ""        # от @TELEGRAM_TOKEN = "8651170126:AAEWaMCIvL0Ur0OUMhBKWgV1uXiPtvSUeqo"

TELEGRAM_CHAT_ID = "6736058409"       # твой Chat ID

SYMBOLS    = ["EURUSD", "GBPUSD", "XAUUSD", "USDJPY"]
TIMEFRAME  = "1h"   # 15m / 1h / 4h / 1d
RR_RATIO   = 2.0    # Risk/Reward
CHECK_EVERY = 300   # каждые 5 минут (секунды)

# ═══════════════════════════════════════════════
#  ПОЛУЧЕНИЕ ДАННЫХ С BINANCE (бесплатно)
# ═══════════════════════════════════════════════
TF_MAP = {"15m": "15m", "1h": "1h", "4h": "4h", "1d": "1d"}

def get_candles(symbol, tf="1h", limit=100):
    """Получаем свечи с Binance"""
    # Конвертируем форекс символы для Binance
    binance_sym = symbol.replace("XAUUSD", "XAUUSDT").replace(
        "EURUSD","EURUSDT").replace("GBPUSD","GBPUSDT").replace(
        "USDJPY","USDTJPY")
    
    # Для форекс пар используем другой источник
    if symbol in ["EURUSD", "GBPUSD", "USDJPY"]:
        return get_forex_candles(symbol, tf, limit)
    
    url = f"https://api.binance.com/api/v3/klines"
    params = {"symbol": binance_sym, "interval": tf, "limit": limit}
    try:
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        candles = []
        for d in data:
            candles.append({
                "open":  float(d[1]),
                "high":  float(d[2]),
                "low":   float(d[3]),
                "close": float(d[4]),
                "vol":   float(d[5])
            })
        return candles
    except Exception as e:
        print(f"Ошибка получения данных {symbol}: {e}")
        return []

def get_forex_candles(symbol, tf, limit):
    """Форекс данные через exchangerate-api"""
    try:
        # Используем twelvedata (бесплатный план)
        url = "https://api.twelvedata.com/time_series"
        params = {
            "symbol": symbol,
            "interval": tf,
            "outputsize": limit,
            "apikey": "demo"  # замени на свой ключ с twelvedata.com (бесплатно)
        }
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        if "values" not in data:
            return get_simulated_candles(symbol)
        candles = []
        for d in reversed(data["values"]):
            candles.append({
                "open":  float(d["open"]),
                "high":  float(d["high"]),
                "low":   float(d["low"]),
                "close": float(d["close"]),
                "vol":   float(d.get("volume", 1000))
            })
        return candles
    except:
        return get_simulated_candles(symbol)

def get_simulated_candles(symbol, count=100):
    """Резервные данные если API недоступно"""
    import random, math
    random.seed(hash(symbol) % 9999)
    base = {"EURUSD":1.085,"GBPUSD":1.265,"USDJPY":148.5,"XAUUSD":2340}
    price = base.get(symbol, 1.0)
    candles = []
    for i in range(count):
        move = (random.random() - 0.48) * price * 0.002
        o = price
        c = o + move
        h = max(o, c) + random.random() * price * 0.001
        l = min(o, c) - random.random() * price * 0.001
        price = c
        candles.append({"open":round(o,5),"high":round(h,5),
                        "low":round(l,5),"close":round(c,5),"vol":1000})
    return candles

# ═══════════════════════════════════════════════
#  SMC АНАЛИЗ
# ═══════════════════════════════════════════════
def get_swing_points(candles, lookback=5):
    swings = []
    for i in range(lookback, len(candles) - lookback):
        hi = candles[i]["high"]
        lo = candles[i]["low"]
        is_high = all(hi > candles[i-j]["high"] and hi > candles[i+j]["high"] for j in range(1, lookback+1))
        is_low  = all(lo < candles[i-j]["low"]  and lo < candles[i+j]["low"]  for j in range(1, lookback+1))
        if is_high: swings.append({"idx": i, "type": "high", "price": hi})
        if is_low:  swings.append({"idx": i, "type": "low",  "price": lo})
    return swings

def get_market_bias(swings):
    highs = [s for s in swings if s["type"] == "high"]
    lows  = [s for s in swings if s["type"] == "low"]
    if len(highs) < 2 or len(lows) < 2:
        return "NEUTRAL"
    hh = highs[-1]["price"] > highs[-2]["price"]
    hl = lows[-1]["price"]  > lows[-2]["price"]
    lh = highs[-1]["price"] < highs[-2]["price"]
    ll = lows[-1]["price"]  < lows[-2]["price"]
    if hh and hl: return "BULLISH"
    if lh and ll: return "BEARISH"
    return "NEUTRAL"

def find_order_block(candles):
    for i in range(2, min(25, len(candles)-2)):
        prev = candles[-(i+1)]
        curr = candles[-i]
        prev_bear = prev["close"] < prev["open"]
        prev_bull = prev["close"] > prev["open"]
        curr_bull = curr["close"] > curr["open"]
        curr_bear = curr["close"] < curr["open"]
        # Bullish OB
        if prev_bear and curr_bull and curr["close"] > prev["high"]:
            return {"type":"BULLISH","high":prev["high"],"low":prev["low"],
                    "mid":(prev["high"]+prev["low"])/2}
        # Bearish OB
        if prev_bull and curr_bear and curr["close"] < prev["low"]:
            return {"type":"BEARISH","high":prev["high"],"low":prev["low"],
                    "mid":(prev["high"]+prev["low"])/2}
    return None

def find_fvg(candles):
    for i in range(1, min(10, len(candles)-1)):
        a = candles[-(i+1)]
        b = candles[-i]
        # Bullish FVG
        if a["high"] < b["low"]:
            return {"type":"BULLISH","top":b["low"],"bottom":a["high"]}
        # Bearish FVG  
        if a["low"] > b["high"]:
            return {"type":"BEARISH","top":a["low"],"bottom":b["high"]}
    return None

def analyze(symbol):
    candles = get_candles(symbol, TIMEFRAME)
    if len(candles) < 30:
        return None

    swings = get_swing_points(candles)
    bias   = get_market_bias(swings)
    ob     = find_order_block(candles)
    fvg    = find_fvg(candles)
    price  = candles[-1]["close"]

    if not ob or bias == "NEUTRAL":
        return None

    # Проверяем что цена в зоне OB
    in_bull_ob = ob["type"] == "BULLISH" and bias == "BULLISH" and ob["low"] <= price <= ob["high"]
    in_bear_ob = ob["type"] == "BEARISH" and bias == "BEARISH" and ob["low"] <= price <= ob["high"]

    if not in_bull_ob and not in_bear_ob:
        return None

    # Расчёт уровней
    if in_bull_ob:
        entry = price
        sl    = ob["low"] - (ob["high"] - ob["low"]) * 0.2
        tp    = entry + (entry - sl) * RR_RATIO
        direction = "BUY"
    else:
        entry = price
        sl    = ob["high"] + (ob["high"] - ob["low"]) * 0.2
        tp    = entry - (sl - entry) * RR_RATIO
        direction = "SELL"

    return {
        "symbol": symbol,
        "direction": direction,
        "bias": bias,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "ob": ob,
        "fvg": fvg,
        "price": price
    }

# ═══════════════════════════════════════════════
#  TELEGRAM
# ═══════════════════════════════════════════════
def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"}
    try:
        r = requests.post(url, data=data, timeout=10)
        return r.status_code == 200
    except Exception as e:
        print(f"Telegram ошибка: {e}")
        return False

def format_signal(sig):
    p = sig["price"]
    digits = 2 if sig["symbol"] in ["XAUUSD","USDJPY"] else 5
    fmt = f"{{:.{digits}f}}"

    emoji = "🟢" if sig["direction"] == "BUY" else "🔴"
    fvg_line = ""
    if sig["fvg"]:
        fvg_line = f"\n💧 *FVG {sig['fvg']['type']}:* {fmt.format(sig['fvg']['bottom'])} – {fmt.format(sig['fvg']['top'])}"

    return (
        f"{emoji} *СИГНАЛ: {sig['direction']}*\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"📌 *Пара:* {sig['symbol']}\n"
        f"⏱ *ТФ:* {TIMEFRAME}\n"
        f"📊 *Структура:* {sig['bias']}\n"
        f"🧱 *OB {sig['ob']['type']}:* {fmt.format(sig['ob']['low'])} – {fmt.format(sig['ob']['high'])}"
        f"{fvg_line}\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"🎯 *Вход:*  {fmt.format(sig['entry'])}\n"
        f"🛑 *Стоп:*  {fmt.format(sig['sl'])}\n"
        f"✅ *Цель:*  {fmt.format(sig['tp'])}\n"
        f"📐 *R/R:* 1:{RR_RATIO}\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"⏰ {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    )

# ═══════════════════════════════════════════════
#  ГЛАВНЫЙ ЦИКЛ
# ═══════════════════════════════════════════════
def main():
    print("🚀 SMC Bot запущен")
    sent_signals = {}
    send_telegram("✅ *SMC Bot запущен!*\nАнализирую: " + ", ".join(SYMBOLS))

    while True:
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Сканирую рынок...")
        for symbol in SYMBOLS:
            try:
                sig = analyze(symbol)
                if sig:
                    key = f"{symbol}_{sig['direction']}_{round(sig['entry'], 3)}"
                    if key not in sent_signals:
                        msg = format_signal(sig)
                        if send_telegram(msg):
                            sent_signals[key] = True
                            print(f"✅ Сигнал отправлен: {symbol} {sig['direction']}")
                        # Не храним больше 50 сигналов
                        if len(sent_signals) > 50:
                            oldest = list(sent_signals.keys())[0]
                            del sent_signals[oldest]
                else:
                    print(f"  {symbol}: нет сигнала")
            except Exception as e:
                print(f"  {symbol}: ошибка {e}")
            time.sleep(2)

        print(f"Следующая проверка через {CHECK_EVERY//60} мин...")
        time.sleep(CHECK_EVERY)

if __name__ == "__main__":
    main()
