import os
import csv
import time
from datetime import datetime

import pandas as pd
from binance.client import Client
from ta.trend import ema_indicator
from ta.momentum import rsi
from binance.enums import *

# ========================
# 1. CONFIGURACIÓN
# ========================
API_KEY = 'Lw3sQdyAZcEJ2s522igX6E28ZL629ZL5JJ9UaqLyM7PXeNRLDu30LmPYFNJ4ixAx'
API_SECRET = 'Adw4DXL2BI9oS4sCJlS3dlBeoJQo6iPezmykfL1bhhm0NQe7aTHpaWULLQ0dYOIt'

symbol = 'APEUSDT'
interval = '5m'
cantidad = 5.50
sl_pct = 0.015  # 1.5%
tp_pct = 0.03  # 3%

client = Client(API_KEY, API_SECRET)
client.API_URL = 'https://fapi.binance.com/fapi'  # Endpoint de futuros

# ========================
# 2. OBTENER DATOS Y CALCULAR INDICADORES
# ========================
def obtener_datos(symbol, interval, limit=100):
    klines = client.futures_klines(symbol=symbol, interval=interval, limit=limit)
    df = pd.DataFrame(klines, columns=[
        'timestamp', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_asset_volume', 'number_of_trades',
        'taker_buy_base', 'taker_buy_quote', 'ignore'
    ])
    df['close'] = df['close'].astype(float)
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    return df

def agregar_indicadores(df):
    df['EMA9'] = ema_indicator(df['close'], window=9)
    df['EMA21'] = ema_indicator(df['close'], window=21)
    df['RSI'] = rsi(df['close'], window=14)
    return df

# ========================
# 3. DETECTAR SEÑAL
# ========================
def detectar_senal(df):
    ultima = df.iloc[-1]
    anterior = df.iloc[-2]
    if anterior['EMA9'] < anterior['EMA21'] and ultima['EMA9'] > ultima['EMA21'] and ultima['RSI'] > 50:
        return 'BUY'
    elif anterior['EMA9'] > anterior['EMA21'] and ultima['EMA9'] < ultima['EMA21'] and ultima['RSI'] < 50:
        return 'SELL'
    return None

# ========================
# 4. REGISTRAR OPERACIÓN
# ========================
def registrar_operacion(symbol, side, entry_price, sl_price, tp_price, quantity, estado='pendiente'):
    archivo = 'registro_operaciones.csv'
    campos = ['timestamp', 'symbol', 'side', 'entry_price', 'sl_price', 'tp_price', 'quantity', 'estado']
    datos = {
        'timestamp': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
        'symbol': symbol,
        'side': side,
        'entry_price': entry_price,
        'sl_price': sl_price,
        'tp_price': tp_price,
        'quantity': quantity,
        'estado': estado
    }
    nuevo = not os.path.exists(archivo)
    with open(archivo, 'a', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=campos)
        if nuevo:
            writer.writeheader()
        writer.writerow(datos)

# ========================
# 5. ABRIR POSICIÓN CON SL Y TP
# ========================

def abrir_posicion_con_sl_tp(symbol, side, quantity, sl_pct, tp_pct):
    try:
        quantity = round(quantity, 2)  # 2 decimales para cantidad

        # Orden MARKET
        client.futures_create_order(
            symbol=symbol,
            side=side.upper(),
            type=ORDER_TYPE_MARKET,
            quantity=quantity
        )
        print(f"✅ Entrada {side} ejecutada.")

        # Precio entrada
        info = client.futures_position_information(symbol=symbol)
        entry_price = float(info[0]['entryPrice'])

        # Calcular SL / TP y redondear a 3 decimales
        if side.upper() == 'BUY':
            sl_price = round(entry_price * (1 - sl_pct), 3)
            tp_price = round(entry_price * (1 + tp_pct), 3)
            close_side = 'SELL'
        else:
            sl_price = round(entry_price * (1 + sl_pct), 3)
            tp_price = round(entry_price * (1 - tp_pct), 3)
            close_side = 'BUY'

        # IMPORTANTE: Convierte a string para evitar problemas de coma flotante
        sl_price = format(sl_price, '.3f')
        tp_price = format(tp_price, '.3f')

        # SL
        client.futures_create_order(
            symbol=symbol,
            side=close_side,
            type='STOP_MARKET',
            stopPrice=sl_price,
            closePosition=True,
            timeInForce='GTC'
        )

        # TP
        client.futures_create_order(
            symbol=symbol,
            side=close_side,
            type='TAKE_PROFIT_MARKET',
            stopPrice=tp_price,
            closePosition=True,
            timeInForce='GTC'
        )

        print(f"🛡️ SL: {sl_price} | 🎯 TP: {tp_price}")
        registrar_operacion(symbol, side, entry_price, sl_price, tp_price, quantity)

    except Exception as e:
        print("❌ Error al ejecutar operación:", e)

# ========================
# 6. LOOP PRINCIPAL
# ========================
if __name__ == '__main__':
    while True:
        try:
            df = obtener_datos(symbol, interval)
            df = agregar_indicadores(df)
            senal = detectar_senal(df)

            if senal:
                print(f"📍 Señal detectada: {senal}")
                abrir_posicion_con_sl_tp(symbol, senal, cantidad, sl_pct, tp_pct)
            else:
                print("⏳ Sin señal clara. Esperando...")

            time.sleep(60 * 5)  # Espera 5 minutos

        except Exception as err:
            print("⚠️ Error en el ciclo principal:", err)
            time.sleep(60)
            