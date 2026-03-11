from investiny import historical_data, search_assets

def obtener_datos_investing(simbolo, intervalo="5", outputsize=50):
    """
    Obtiene datos de Investing.com usando investiny.
    Args:
        simbolo: Símbolo del activo (ej. "XAUUSD", "WTI", "US100")
        intervalo: Intervalo en minutos (1, 5, 15, 30, 60)
        outputsize: Número de velas a obtener
    """
    try:
        # Primero, buscar el activo para obtener su investing_id
        search_results = search_assets(query=simbolo, limit=1)
        if not search_results:
            print(f"Activo {simbolo} no encontrado")
            return None
        
        investing_id = int(search_results[0]["ticker"])
        
        # Calcular fechas (últimos 'outputsize' intervalos)
        from datetime import datetime, timedelta
        end_date = datetime.now()
        # Necesitamos calcular la fecha de inicio basada en el intervalo
        # Esto es una simplificación; en producción ajusta según necesidad
        start_date = end_date - timedelta(minutes=outputsize * int(intervalo))
        
        # Formatear fechas como "dd/mm/aaaa"
        from_date = start_date.strftime("%d/%m/%Y")
        to_date = end_date.strftime("%d/%m/%Y")
        
        # Obtener datos históricos
        data = historical_data(
            investing_id=investing_id,
            from_date=from_date,
            to_date=to_date
        )
        
        if not data:
            return None
        
        # Convertir a DataFrame
        df = pd.DataFrame(data)
        
        # Renombrar columnas al formato esperado por calcular_indicadores
        df = df.rename(columns={
            'open': 'open',
            'high': 'high',
            'low': 'low',
            'close': 'close',
            'volume': 'volume'
        })
        
        # Asegurar tipos numéricos
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Convertir índice datetime si existe
        if 'date' in df.columns:
            df['datetime'] = pd.to_datetime(df['date'])
            df = df.set_index('datetime')
        
        return df
        
    except Exception as e:
        print(f"Error con investiny para {simbolo}: {e}")
        return None

# Luego, en tu función get_senal y en el bucle, reemplaza obtener_datos_twelvedata por obtener_datos_investing
