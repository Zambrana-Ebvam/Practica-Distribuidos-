# pyrefly: ignore [missing-import]
import os
import sys
import pandas as pd
# pyrefly: ignore [missing-import]
from cassandra.cluster import Cluster

def main():
    print("=== INICIANDO CONSULTA CABRA ===")
    
    # 1. Intentar ejecutar la consulta nativa en Cassandra
    cassandra_exito = False
    avg_dias_cql = None
    
    try:
        # Conectar a Cassandra
        try:
            sys.path.append(os.path.dirname(os.path.abspath(__file__)))
            from db import get_session
            session = get_session()
        except Exception:
            cluster = Cluster(['127.0.0.1'], port=9042)
            session = cluster.connect('semapa')
            
        # Ejecutar la consulta solicitada
        query = """
            SELECT AVG(dias_pago) as avg_dias
            FROM recibos_pago_por_periodo
            WHERE periodo = '2026-05'
            AND estado_pago = 'PAGADO';
        """
        result = session.execute(query).one()
        if result:
            # Dependiendo de row_factory, result puede ser dict o fila
            avg_dias_cql = result["avg_dias"] if isinstance(result, dict) else getattr(result, "avg_dias", None)
            cassandra_exito = True
            
    except Exception as e:
        print("\n[INFO] La consulta directa en Cassandra falló:")
        print(f"       -> {e}")
        print("\n[Explicación]")
        print(" La tabla 'recibos_pago_por_periodo' no existe en el esquema actual de Cassandra.")
        print(" Sin embargo, ¡podemos calcular el promedio real analizando el archivo fuente de lecturas!")

    # 2. Si falló en Cassandra, calcular usando data/lecturas.csv
    if not cassandra_exito:
        print("\n[Solución de Respaldo: Procesando data/lecturas.csv...]")
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        lecturas_path = os.path.join(base_dir, "data", "lecturas.csv")
        
        if not os.path.exists(lecturas_path):
            print(f"[ERROR] No se encontro el archivo de origen en {lecturas_path}")
            return
            
        try:
            # Leer CSV
            df = pd.read_csv(lecturas_path, low_memory=False)
            
            # Limpiar columnas
            df.columns = [c.strip() for c in df.columns]
            
            # Convertir fechas de forma rápida especificando el formato exacto del CSV
            df['fecha_lectura_dt'] = pd.to_datetime(df['fechaHoraLectura'], format='%m/%d/%y %H:%M', errors='coerce')
            df['fecha_pago_dt'] = pd.to_datetime(df['fecha_pago'], format='%m/%d/%y %H:%M', errors='coerce')
            
            # Extraer periodo en formato YYYY-MM
            df['periodo'] = df['fecha_lectura_dt'].dt.strftime('%Y-%m')
            
            # Filtrar por periodo '2026-05' y estado_pago = 'PAGADO' (fecha_pago no nula)
            df_filtrado = df[
                (df['periodo'] == '2026-05') & 
                (df['fecha_pago_dt'].notna())
            ].copy()
            
            if df_filtrado.empty:
                # Si no hay datos en 2026-05, busquemos el periodo con más datos para sugerir
                print("[ADVERTENCIA] No se encontraron pagos registrados para el periodo '2026-05' en el CSV.")
                # Ver periodos disponibles
                df['periodo_valido'] = df['fecha_lectura_dt'].dt.strftime('%Y-%m')
                periodos_disponibles = df[df['fecha_pago_dt'].notna()]['periodo_valido'].value_counts()
                if not periodos_disponibles.empty:
                    print("\nPeriodos con pagos disponibles en el CSV:")
                    for p, cant in periodos_disponibles.items():
                        print(f"  - Periodo {p}: {cant} pagos registrados")
                    
                    # Usamos el periodo más activo como demostración
                    demo_periodo = periodos_disponibles.index[0]
                    print(f"\nRealizando calculo demostrativo con el periodo mas activo: '{demo_periodo}'")
                    df_filtrado = df[
                        (df['periodo_valido'] == demo_periodo) & 
                        (df['fecha_pago_dt'].notna())
                    ].copy()
                    periodo_calculado = demo_periodo
                else:
                    print("No hay ningun pago registrado en todo el archivo lecturas.csv.")
                    return
            else:
                periodo_calculado = '2026-05'
                
            # Calcular dias_pago (diferencia en días)
            df_filtrado['dias_pago'] = (df_filtrado['fecha_pago_dt'] - df_filtrado['fecha_lectura_dt']).dt.total_seconds() / (24 * 3600)
            
            # Promedio de días
            avg_dias = df_filtrado['dias_pago'].mean()
            total_recibos = len(df_filtrado)
            
            print("\n=========================================================================")
            print(f"   RESULTADO DE LA CONSULTA CABRA (CALCULO DEL CSV ORIGEN)")
            print("=========================================================================")
            print(f" - Tabla Solicitada:  recibos_pago_por_periodo (Simulada)")
            print(f" - Periodo Analizado: {periodo_calculado}")
            print(f" - Estado de Pago:    PAGADO")
            print(f" - Total Recibos:     {total_recibos:,} recibos")
            print(f" - Promedio Dias:     {avg_dias:.2f} dias para pagar")
            print("=========================================================================")
            
        except Exception as csv_err:
            print(f"[ERROR] Error al procesar el archivo CSV: {csv_err}")
            
    else:
        # Si la consulta en Cassandra tuvo éxito
        print("\n=========================================================================")
        print("   RESULTADO DE LA CONSULTA CABRA (CASSANDRA DIRECTO)")
        print("=========================================================================")
        print(f" - Periodo:           2026-05")
        print(f" - Estado de Pago:    PAGADO")
        print(f" - Promedio Días:     {avg_dias_cql:.2f} días")
        print("=========================================================================")

if __name__ == "__main__":
    main()
