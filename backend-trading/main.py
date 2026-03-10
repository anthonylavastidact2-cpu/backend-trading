# main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import ta
from ta.volatility import AverageTrueRange
from ta.trend import EMAIndicator
from ta.momentum import RSIIndicator
import requests
import asyncio
import telegram
import os

# ===================== CONFIGURACIÓN =====================
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "TU_TOKEN_AQUI")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "TU_CHAT_ID_AQUI")
TWELVEDATA_API_KEY = os.environ.get("TWELVEDATA_API_KEY", "TU_API_KEY")

app = FastAPI()

# Permitir que tu página web (GitHub Pages) llame a esta API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, pondrías la URL de tu GitHub Pages
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===================== FUNCIONES DE ESTRATEGIAS =====================
def calcular_indicadores(df):
    if df is None or len(df) < 20:
        return None
    df = df.copy()
    df.columns = [c.lower() for c in df.columns]
    df['rsi'] = RSIIndicator(df['close'], window=14).rsi()
    df['ema_20'] = EMAIndicator(df['close'], window=20).ema_indicator()
    atr = AverageTrueRange(df['high'], df['low'], df['close'], window=14)
    df['atr'] = atr.average_true_range()
    df['atr_pct'] = (df['atr'] / df['close']) * 100
    return df

def detectar_senal_apalancamiento(df):
    if df is None:
        return None
    ultimo = df.iloc[-1]
    # Señal de COMPRA
    if 30 <= ultimo['rsi'] <= 45 and ultimo['close'] > ultimo['ema_20'] and ultimo['atr_pct'] > 0.5:
        precio = round(ultimo['close'], 2)
        return {
            'tipo': 'CALL',
            'precio': precio,
            'tp1': round(precio * 1.02, 2),
            'tp2': round(precio * 1.04, 2),
            'confianza': 'ALTA'
        }
    # Señal de VENTA
    if 55 <= ultimo['rsi'] <= 70 and ultimo['close'] < ultimo['ema_20'] and ultimo['atr_pct'] > 0.5:
        precio = round(ultimo['close'], 2)
        return {
            'tipo': 'PUT',
            'precio': precio,
            'tp1': round(precio * 0.98, 2),
            'tp2': round(precio * 0.96, 2),
            'confianza': 'ALTA'
        }
    return None

def detectar_senal_binarias(df):
    if df is None:
        return None
    ultimo = df.iloc[-1]
    if 40 <= ultimo['rsi'] <= 60 and ultimo['close'] > ultimo['ema_20']:
        return {
            'tipo': 'CALL',
            'precio': round(ultimo['close'], 2),
            'duracion': '5-15 min'
        }
    if 40 <= ultimo['rsi'] <= 60 and ultimo['close'] < ultimo['ema_20']:
        return {
            'tipo': 'PUT',
            'precio': round(ultimo['close'], 2),
            'duracion': '5-15 min'
        }
    return None

# ===================== FUNCIÓN PARA OBTENER DATOS =====================
def obtener_datos_twelvedata(simbolo, intervalo="5min", outputsize=50):
    url = "https://api.twelvedata.com/time_series"
    params = {
        "apikey": TWELVEDATA_API_KEY,
        "symbol": simbolo,
        "interval": intervalo,
        "outputsize": outputsize,
        "format": "JSON"
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        if "values" not in data:
            return None
        df = pd.DataFrame(data["values"])
        df["datetime"] = pd.to_datetime(df["datetime"])
        df = df.sort_values("datetime")
        df[["open", "high", "low", "close"]] = df[["open", "high", "low", "close"]].astype(float)
        df.columns = [c.lower() for c in df.columns]
        return df
    except Exception as e:
        print(f"Error con {simbolo}: {e}")
        return None

# ===================== ENDPOINTS DE LA API =====================
@app.get("/")
def home():
    return {"mensaje": "API de Trading funcionando"}

@app.get("/senal/{activo}")
async def get_senal(activo: str):
    """Devuelve la señal actual para un activo (ej. XAUUSD)"""
    df = obtener_datos_twelvedata(activo)
    if df is None:
        return {"error": "No se pudieron obtener datos"}
    df = calcular_indicadores(df)
    senal_ap = detectar_senal_apalancamiento(df)
    senal_bin = detectar_senal_binarias(df)
    return {
        "activo": activo,
        "apalancamiento": senal_ap,
        "binarias": senal_bin
    }

@app.get("/enviar-telegram")
async def enviar_telegram(mensaje: str):
    """Envía un mensaje de prueba a Telegram"""
    try:
        bot = telegram.Bot(token=TELEGRAM_TOKEN)
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=mensaje)
        return {"ok": True}
    except Exception as e:
        return {"error": str(e)}

# ===================== TAREA AUTOMÁTICA CADA 5 MINUTOS =====================
# Esto se ejecutará cuando el backend esté activo
import threading
import time

def bucle_senales():
    activos = ["XAUUSD", "WTI", "US100"]
    while True:
        for activo in activos:
            try:
                df = obtener_datos_twelvedata(activo)
                if df is not None:
                    df = calcular_indicadores(df)
                    senal_ap = detectar_senal_apalancamiento(df)
                    senal_bin = detectar_senal_binarias(df)
                    if senal_ap or senal_bin:
                        # Enviar a Telegram
                        mensaje = f"🔔 *{activo}*\n"
                        if senal_ap:
                            mensaje += f"📈 Apalancamiento: {senal_ap['tipo']} a ${senal_ap['precio']}\n"
                        if senal_bin:
                            mensaje += f"⏱ Binarias: {senal_bin['tipo']} a ${senal_bin['precio']}\n"
                        asyncio.run(enviar_telegram_coroutine(mensaje))
            except Exception as e:
                print(f"Error en {activo}: {e}")
            time.sleep(2)  # Pequeña pausa entre activos
        time.sleep(300)   # 5 minutos

def iniciar_bucle():
    thread = threading.Thread(target=bucle_senales, daemon=True)
    thread.start()

@app.on_event("startup")
def startup_event():
    iniciar_bucle()