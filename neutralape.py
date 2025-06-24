import time
import pandas as pd
import numpy as np
from binance.client import Client
from binance.enums import *
from datetime import datetime
import csv
import os

# ======== CONFIGURACIÓN ========
api_key = 'Lw3sQdyAZcEJ2s522igX6E28ZL629ZL5JJ9UaqLyM7PXeNRLDu30LmPYFNJ4ixAx'
api_secret = 'Adw4DXL2BI9oS4sCJlS3dlBeoJQo6iPezmykfL1bhhm0NQe7aTHpaWULLQ0dYOIt'
symbol = 'APEUSDT'
intervalo = '5m'
cantidad_usdt = 6  # Capital por operación
take_profit_pct = 0.015  # 1.5%
stop_loss_pct = 0.005   # 0.5%
# ===============================

client = Client(api_key, api_secret)
client.API_URL = 'https://fapi.binance.com/fapi'  # FUTUROS

def obtener_datos(symbol, intervalo, limite=100):
    klines = client.futures_klines(symbol=symbol, interval=intervalo, limit=limite)
    df = pd.DataFrame(klines, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume',
                                       'close_time', 'quote_asset_volume', 'number_of_trades',
                                       'taker_buy_base', 'taker_buy_quote', 'ignore'])
    df['close'] = df['close'].astype(float)
    df['high'] = df['high'].astype(float)
    df['low'] = df['low'].astype(float)
    return df[['close', 'high', 'low']]

def calcular_senal(df):
    df['ma'] = df['close'].rolling(window=20).mean()
    df['std'] = df['close'].rolling(window=20).std()
    df['upper'] = df['ma'] + 2 * df['std']
    df['lower'] = df['ma'] - 2 * df['std']

    # Detectar cruce hacia arriba de la banda superior (longCond en Pine Script)
    if len(df) < 2:
        return 'neutral'
    close_prev = df['close'].iloc[-2]
    close_now = df['close'].iloc[-1]
    upper_prev = df['upper'].iloc[-2]
    upper_now = df['upper'].iloc[-1]
    lower_prev = df['lower'].iloc[-2]
    lower_now = df['lower'].iloc[-1]

    # Cruce hacia arriba de la banda superior (long)
    if close_prev <= upper_prev and close_now > upper_now:
        return 'long'
    # Cruce hacia abajo de la banda inferior (short)
    elif close_prev >= lower_prev and close_now < lower_now:
        return 'short'
    else:
        return 'neutral'

def calcular_cantidad(symbol, usdt_amount):
    precio = float(client.futures_symbol_ticker(symbol=symbol)['price'])
    info = client.futures_exchange_info()
    step_size = 0.01
    for s in info['symbols']:
        if s['symbol'] == symbol:
            for f in s['filters']:
                if f['filterType'] == 'LOT_SIZE':
                    step_size = float(f['stepSize'])
    cantidad = usdt_amount / precio
    precision = int(round(-np.log10(step_size)))
    return round(cantidad, precision)

def calcular_cantidad_riesgo(saldo_usdt, riesgo_pct, distancia_sl, precio):
    riesgo_usdt = saldo_usdt * riesgo_pct
    if distancia_sl == 0:
        return 0
    cantidad = riesgo_usdt / distancia_sl
    return round(cantidad, 3)

def ejecutar_orden(senal, symbol, usdt_amount):
    try:
        cantidad = calcular_cantidad(symbol, usdt_amount)
        if cantidad == 0:
            print("❌ La cantidad calculada es 0. No se ejecuta la orden.")
            return None, None

        # Verifica saldo disponible (opcional, solo si quieres mayor seguridad)
        # balance = client.futures_account_balance()
        # saldo_usdt = next((float(b['balance']) for b in balance if b['asset'] == 'USDT'), 0)
        # if saldo_usdt < usdt_amount:
        #     print(f"❌ Saldo insuficiente: tienes {saldo_usdt} USDT, necesitas {usdt_amount} USDT.")
        #     return None, None

        side = SIDE_BUY if senal == 'long' else SIDE_SELL
        try:
            orden = client.futures_create_order(
                symbol=symbol,
                side=side,
                type=ORDER_TYPE_MARKET,
                quantity=cantidad
            )
        except Exception as e:
            print(f"❌ Error al crear la orden de mercado: {e}")
            return None, None

        # Verifica que la posición realmente se abrió
        info_pos = client.futures_position_information(symbol=symbol)
        if not info_pos or float(info_pos[0]['positionAmt']) == 0:
            print("❌ La orden fue enviada pero no se abrió posición. Puede ser por cantidad mínima o error de Binance.")
            return None, None

        precio = float(info_pos[0]['entryPrice'])
        print(f"✅ Operación {senal.upper()} ejecutada a {precio}")
        return precio, cantidad

    except Exception as e:
        print(f"❌ Error inesperado al ejecutar operación: {e}")
        return None, None

def registrar_operacion(fecha, tipo, precio_entrada, cantidad, tp, sl):
    archivo = 'registro_operaciones.csv'
    existe = os.path.isfile(archivo)
    with open(archivo, mode='a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if not existe:
            writer.writerow(['Fecha', 'Tipo', 'Precio Entrada', 'Cantidad', 'Take Profit', 'Stop Loss'])
        writer.writerow([fecha, tipo, precio_entrada, cantidad, tp, sl])

def obtener_capital_operacion(porcentaje=0.05):
    balance = client.futures_account_balance()
    saldo_usdt = next((float(b['balance']) for b in balance if b['asset'] == 'USDT'), 0)
    capital = max(round(saldo_usdt * porcentaje, 2), 5)  # Nunca menos de 5 USDT
    print(f"💰 Saldo disponible: {saldo_usdt} USDT | Usando {capital} USDT para la operación ({int(porcentaje*100)}%)")
    return capital

def calcular_atr(df, periodo=14):
    df['high'] = df['high'].astype(float)
    df['low'] = df['low'].astype(float)
    df['close'] = df['close'].astype(float)
    df['tr'] = df[['high', 'low', 'close']].apply(
        lambda row: max(row['high'] - row['low'], abs(row['high'] - row['close']), abs(row['low'] - row['close'])), axis=1)
    df['atr'] = df['tr'].rolling(window=periodo).mean()
    return df['atr'].iloc[-1]

def obtener_precisiones(symbol):
    info = client.futures_exchange_info()
    cantidad_decimales = 3
    precio_decimales = 3
    for s in info['symbols']:
        if s['symbol'] == symbol:
            for f in s['filters']:
                if f['filterType'] == 'LOT_SIZE':
                    step_size = float(f['stepSize'])
                    cantidad_decimales = abs(int(np.log10(step_size)))
                if f['filterType'] == 'PRICE_FILTER':
                    tick_size = float(f['tickSize'])
                    precio_decimales = abs(int(np.log10(tick_size)))
    return cantidad_decimales, precio_decimales

# ============ LOOP PRINCIPAL ============
while True:
    df = obtener_datos(symbol, intervalo)

    if len(df) < 20:
        print("⏳ Esperando más datos...")
        time.sleep(60)
        continue

    senal = calcular_senal(df)
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Señal detectada: {senal.upper()}")

    info_pos = client.futures_position_information(symbol=symbol)
    if not info_pos:
        print("Sin posición abierta.")
        pos_abierta = 0.0
    else:
        posicion = info_pos[0]
        pos_abierta = float(posicion['positionAmt'])
        if pos_abierta != 0:
            print(f"Posición actual: cantidad={posicion['positionAmt']}, precio entrada={posicion['entryPrice']}, PnL={posicion['unRealizedProfit']}")
        else:
            print("Sin posición abierta.")

    # Evitar duplicar posiciones en la misma dirección
    if (senal == 'long' and pos_abierta > 0) or (senal == 'short' and pos_abierta < 0):
        print("⚠️ Ya hay una posición abierta en la misma dirección. No se ejecuta nueva orden.")
        time.sleep(60)
        continue

    # === Gestión dinámica y avanzada ===
    if senal in ['long', 'short'] and pos_abierta == 0:
        atr = calcular_atr(df)
        umbral_volatilidad = 0.02  # Ajusta este valor según tu experiencia

        if atr > umbral_volatilidad:
            print("Mercado demasiado volátil, no se opera.")
            time.sleep(60)
            continue

        # Gestión de riesgo avanzada
        balance = client.futures_account_balance()
        saldo_usdt = next((float(b['balance']) for b in balance if b['asset'] == 'USDT'), 0)
        riesgo_pct = 0.01  # 1% de riesgo por operación

        # Calcula distancia SL en precio (más amplio)
        precio_actual = float(df['close'].iloc[-1])
        if senal == 'long':
            sl = precio_actual - atr * 1.5
            tp = precio_actual + atr * 2
            distancia_sl = atr * 1.5
        else:
            sl = precio_actual + atr * 1.5
            tp = precio_actual - atr * 2
            distancia_sl = atr * 1.5

        # Redondeo de precios y cantidad según precisión del símbolo
        cantidad_decimales, precio_decimales = obtener_precisiones(symbol)
        cantidad = calcular_cantidad_riesgo(saldo_usdt, riesgo_pct, distancia_sl, precio_actual)
        cantidad = round(cantidad, cantidad_decimales)
        sl = round(sl, precio_decimales)
        tp = round(tp, precio_decimales)

        print(f"💰 Saldo disponible: {saldo_usdt} USDT | Usando {cantidad} contratos para la operación ({riesgo_pct*100:.1f}% de riesgo, SL={sl:.4f}, TP={tp:.4f})")

        precio_entrada, cantidad_real = ejecutar_orden(senal, symbol, cantidad)

        if precio_entrada:
            # Cancelar órdenes TP/SL abiertas antes de crear nuevas
            ordenes_abiertas = client.futures_get_open_orders(symbol=symbol)
            for orden in ordenes_abiertas:
                if orden['type'] in ['STOP_MARKET', 'TAKE_PROFIT_MARKET']:
                    try:
                        client.futures_cancel_order(symbol=symbol, orderId=orden['orderId'])
                    except Exception as e:
                        print(f"❌ Error al cancelar orden previa: {e}")

            # Crear TP/SL según la dirección de la señal
            try:
                if senal == 'long':
                    client.futures_create_order(
                        symbol=symbol,
                        side='SELL',
                        type='TAKE_PROFIT_MARKET',
                        stopPrice=tp,
                        quantity=cantidad_real,
                        reduceOnly=True
                    )
                    client.futures_create_order(
                        symbol=symbol,
                        side='SELL',
                        type='STOP_MARKET',
                        stopPrice=sl,
                        quantity=cantidad_real,
                        reduceOnly=True
                    )
                else:
                    client.futures_create_order(
                        symbol=symbol,
                        side='BUY',
                        type='TAKE_PROFIT_MARKET',
                        stopPrice=tp,
                        quantity=cantidad_real,
                        reduceOnly=True
                    )
                    client.futures_create_order(
                        symbol=symbol,
                        side='BUY',
                        type='STOP_MARKET',
                        stopPrice=sl,
                        quantity=cantidad_real,
                        reduceOnly=True
                    )
            except Exception as e:
                print(f"❌ Error al crear TP/SL: {e}")

            registrar_operacion(
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                senal,
                precio_entrada,
                cantidad_real,
                tp,
                sl
            )
            print(f"✅ Orden {senal.upper()} ejecutada correctamente.")
            print(f"🎯 Take Profit: {tp:.4f} | 🛑 Stop Loss: {sl:.4f}")
        else:
            print(f"❌ No se pudo ejecutar la orden {senal.upper()}.")

    time.sleep(60)  # Esperar antes de la siguiente verificación
