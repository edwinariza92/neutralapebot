from binance.client import Client

api_key = 'Lw3sQdyAZcEJ2s522igX6E28ZL629ZL5JJ9UaqLyM7PXeNRLDu30LmPYFNJ4ixAx'
api_secret = 'Adw4DXL2BI9oS4sCJlS3dlBeoJQo6iPezmykfL1bhhm0NQe7aTHpaWULLQ0dYOIt'

client = Client(api_key, api_secret)
client.API_URL = 'https://fapi.binance.com/fapi'  # FUTUROS

try:
    # Prueba de conexión general
    info = client.futures_account()
    print("✅ Conexión exitosa a Binance Futuros.")
    print(f"Permisos de API: {info['canTrade']=}, {info['canDeposit']=}, {info['canWithdraw']=}")
except Exception as e:
    print(f"❌ Error de conexión o permisos: {e}")

try:
    # Prueba de consulta de precios
    ticker = client.futures_symbol_ticker(symbol='APEUSDT')
    print(f"✅ Precio actual APEUSDT: {ticker['price']}")
except Exception as e:
    print(f"❌ No se pudo obtener el precio de APEUSDT: {e}")

try:
    # Prueba de consulta de posiciones (no requiere tener posiciones abiertas)
    posiciones = client.futures_position_information(symbol='APEUSDT')
    print(f"✅ Consulta de posiciones exitosa. Resultado: {posiciones}")
except Exception as e:
    print(f"❌ No se pudo consultar posiciones: {e}")