# pyrefly: ignore [missing-import]
import os
import sys
# pyrefly: ignore [missing-import]
from cassandra.cluster import Cluster

def main():
    print("=== INICIANDO CONSULTA MERUVIA (GRUPO Y AGREGACION) ===")
    
    # 1. Intentar conectar a Cassandra
    try:
        try:
            sys.path.append(os.path.dirname(os.path.abspath(__file__)))
            from db import get_session
            session = get_session()
            print("-> Conectado exitosamente usando la configuracion de db.py")
        except Exception:
            cluster = Cluster(['127.0.0.1'], port=9042)
            session = cluster.connect('semapa')
            print("-> Conectado exitosamente a Cassandra en localhost:9042")

        print("\n[Explicacion de Cassandra/CQL]")
        print("La consulta CQL solicitada:")
        print("  \"SELECT categoria, SUM(consumo_m3) as total_consumo, SUM(total_cuentas) as total_cuentas")
        print("   FROM consumo_categoria_distrito_mes")
        print("   GROUP BY categoria;\"")
        print("\nNo se puede ejecutar de forma directa en Cassandra debido a sus restricciones de diseno:")
        print(" 1. GROUP BY solo es permitido en Cassandra si se restringen todas las columnas de la clave de particion")
        print("    en la clausula WHERE con operadores de igualdad (por ejemplo: WHERE distrito = 'X' AND periodo = 'Y').")
        print(" 2. No se puede agrupar globalmente a traves de multiples particiones sin un filtro de particion previo.")
        print("\n[Solucion Aplicada]")
        print("Dado que 'consumo_categoria_distrito_mes' es una tabla agregada pequena, realizamos la consulta adaptada:")
        print(" 1. Recuperamos todos los registros agregados de la tabla.")
        print(" 2. Realizamos la agrupacion (GROUP BY categoria) y sumas en memoria usando Python de forma ultra rapida.")

        # 2. Ejecutar consulta adaptada
        query = """
            SELECT categoria, consumo_m3, total_cuentas 
            FROM consumo_categoria_distrito_mes;
        """
        rows = session.execute(query)
        
        # 3. Agrupación y sumas en memoria
        agrupado = {}
        
        for r in rows:
            # Detectar formato de fila según row_factory
            if isinstance(r, dict):
                cat = r["categoria"] or "SIN CATEGORIA"
                consumo = float(r["consumo_m3"] or 0.0)
                cuentas = int(r["total_cuentas"] or 0)
            else:
                cat = r.categoria or "SIN CATEGORIA"
                consumo = float(r.consumo_m3 or 0.0)
                cuentas = int(r.total_cuentas or 0)
                
            if cat not in agrupado:
                agrupado[cat] = {
                    "total_consumo": 0.0,
                    "total_cuentas": 0
                }
                
            agrupado[cat]["total_consumo"] += consumo
            agrupado[cat]["total_cuentas"] += cuentas

        if not agrupado:
            print("\n[ADVERTENCIA] No se encontraron registros en la base de datos.")
            return

        # 4. Imprimir los resultados en una tabla premium y elegante
        print("\n=========================================================================")
        print("   RESULTADO DE LA CONSULTA MERUVIA: CONSUMO TOTAL POR CATEGORIA")
        print("=========================================================================")
        print(f"{'Categoria':<25} | {'Consumo Total (m3)':<20} | {'Total Cuentas':<15}")
        print("-" * 72)
        
        # Ordenamos las categorías alfabéticamente para mejor visualización
        for cat, datos in sorted(agrupado.items()):
            print(f"{cat:<25} | {datos['total_consumo']:<20,.2f} | {datos['total_cuentas']:<15,}")
        print("=========================================================================")
        print("¡Consulta completada con exito!")

    except Exception as e:
        print(f"\n[ERROR] Error al ejecutar la consulta: {e}")

if __name__ == "__main__":
    main()
