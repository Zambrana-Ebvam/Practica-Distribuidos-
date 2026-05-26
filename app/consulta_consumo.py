# pyrefly: ignore [missing-import]
from cassandra.cluster import Cluster

def main():
    try:
        # Nos conectamos a Cassandra en localhost:9042
        cluster = Cluster(['127.0.0.1'], port=9042)
        session = cluster.connect('semapa')
        
        # Consultamos el consumo total por distrito y periodo (mes)
        query = "SELECT distrito, periodo, consumo_m3 FROM consumo_distrito_mes;"
        rows = session.execute(query)
        
        data = {}
        for row in rows:
            dist = row.distrito
            if dist not in data:
                data[dist] = {}
            data[dist][row.periodo] = row.consumo_m3
        
        print("\n=== REPORTE DE CONSUMO DE AGUA POR DISTRITO (ÚLTIMOS 3 MESES) ===")
        print(f"{'Distrito':<10} | {'Febrero 2026':<16} | {'Marzo 2026':<16} | {'Abril 2026':<16}")
        print("-" * 68)
        
        # Ordenamos los distritos de forma numérica
        distritos_ordenados = sorted(data.keys(), key=lambda x: int(x) if x.isdigit() else x)
        
        for dist in distritos_ordenados:
            m1 = f"{data[dist].get('2026-02', 0.0):,.2f} m³"
            m2 = f"{data[dist].get('2026-03', 0.0):,.2f} m³"
            m3 = f"{data[dist].get('2026-04', 0.0):,.2f} m³"
            print(f"Distrito {dist:<2} | {m1:<16} | {m2:<16} | {m3:<16}")
        print("-" * 68)
        
        cluster.shutdown()
    except Exception as e:
        print(f"Error al conectar con Cassandra: {e}")

if __name__ == '__main__':
    main()
