# pyrefly: ignore [missing-import]
import sys
# pyrefly: ignore [missing-import]
from cassandra.cluster import Cluster

TARIFAS_BS = {
    "RESIDENCIAL": 2.80,
    "COMERCIAL": 10.43,
    "COMERCIAL ESPECIAL": 12.16,
    "INDUSTRIAL": 9.39,
    "PREFERENCIAL": 4.58,
    "SOCIAL": 7.64,
    "R1": 1.39,
    "R2": 2.78,
    "R3": 5.21,
    "R4": 8.69,
    "C": 10.43,
    "CE": 12.16,
    "I": 9.39,
    "P": 4.58,
    "S": 7.64
}

def normalizar_texto(value):
    if value is None:
        return ""
    text = str(value).strip().upper()
    replacements = {
        "Á": "A", "É": "E", "Í": "I", "Ó": "O", "Ú": "U", "Ñ": "N"
    }
    for wrong, right in replacements.items():
        text = text.replace(wrong, right)
    return text

def tarifa_categoria(categoria, subcategoria=None):
    cat = normalizar_texto(categoria)
    sub = normalizar_texto(subcategoria)

    if sub in TARIFAS_BS:
        return TARIFAS_BS[sub]

    if cat in TARIFAS_BS:
        return TARIFAS_BS[cat]

    if "RESIDENCIAL" in cat:
        return TARIFAS_BS["RESIDENCIAL"]
    if "COMERCIAL ESPECIAL" in cat:
        return TARIFAS_BS["COMERCIAL ESPECIAL"]
    if "COMERCIAL" in cat:
        return TARIFAS_BS["COMERCIAL"]
    if "INDUSTRIAL" in cat:
        return TARIFAS_BS["INDUSTRIAL"]
    if "PREFERENCIAL" in cat:
        return TARIFAS_BS["PREFERENCIAL"]
    if "SOCIAL" in cat:
        return TARIFAS_BS["SOCIAL"]

    return 3.00

def main():
    # Permitimos pasar el periodo como argumento, por defecto usamos '2026-04' que tiene datos
    # (El periodo '2025-01' no tiene registros en la base de datos actual)
    periodo = '2026-04'
    if len(sys.argv) > 1:
        periodo = sys.argv[1]

    print(f"=== INICIANDO CONSULTA 2 (Periodo seleccionado: {periodo}) ===")
    
    try:
        cluster = Cluster(['127.0.0.1'], port=9042)
        session = cluster.connect('semapa')
        
        # ----------------------------------------------------
        # Paso 1: Obtener cuentas del Distrito 5
        # ----------------------------------------------------
        print("\nPaso 1: Consultando cuentas del Distrito 5 en Cassandra...")
        query_cuentas = """
            SELECT cuenta_id, zona, estado_contrato, categoria, subcategoria 
            FROM cuentas_por_distrito 
            WHERE distrito = '5';
        """
        rows = session.execute(query_cuentas)
        
        morosos = {
            "MOROSO", "CORTADO", "SUSPENDIDO", "SUSPENDIDA", 
            "BAJA", "INACTIVO", "INACTIVA"
        }
        
        cuentas_morosas = []
        for r in rows:
            estado = normalizar_texto(r.estado_contrato)
            if estado in morosos:
                cuentas_morosas.append({
                    "cuenta_id": r.cuenta_id,
                    "zona": r.zona or "SIN ZONA",
                    "categoria": r.categoria,
                    "subcategoria": r.subcategoria
                })
        
        total_cuentas = len(cuentas_morosas)
        print(f"-> Se encontraron {total_cuentas} cuentas en estado MOROSO/INACTIVO.")
        
        if total_cuentas == 0:
            print("No se encontraron cuentas morosas. Fin del proceso.")
            cluster.shutdown()
            return
            
        # ----------------------------------------------------
        # Paso 2: Obtener consumo de cada cuenta en el periodo
        # ----------------------------------------------------
        print(f"\nPaso 2: Consultando consumos del periodo '{periodo}' de forma asíncrona...")
        
        # Preparamos la consulta para máxima eficiencia
        stmt_consumo = session.prepare("""
            SELECT consumo_m3 
            FROM consumo_cuenta_mes 
            WHERE cuenta_id = ? AND periodo = ?;
        """)
        
        # Lanzamos las consultas de forma asíncrona (asynchronous execution) 
        # para evitar el cuello de botella secuencial.
        futures = []
        for c in cuentas_morosas:
            future = session.execute_async(stmt_consumo, (c["cuenta_id"], periodo))
            futures.append((c, future))
            
        # Recolectamos los resultados de los consumos
        cuentas_con_consumo = []
        consultas_completadas = 0
        
        for c, future in futures:
            try:
                res_row = future.result().one()
                consultas_completadas += 1
                
                # Imprimir progreso cada 2000 consultas
                if consultas_completadas % 2000 == 0:
                    print(f"   Procesando... {consultas_completadas}/{total_cuentas}")
                    
                if res_row:
                    consumo = float(res_row.consumo_m3 or 0.0)
                    c["consumo_m3"] = consumo
                    cuentas_con_consumo.append(c)
            except Exception as e:
                print(f"Error al obtener consumo de cuenta {c['cuenta_id']}: {e}")
                
        print(f"-> Se recuperaron consumos activos para {len(cuentas_con_consumo)} cuentas morosas.")
        
        # ----------------------------------------------------
        # Paso 3: Sumar consumo_m3 * tarifa por zona
        # ----------------------------------------------------
        print("\nPaso 3: Calculando facturación simulada (consumo * tarifa) por zona...")
        
        facturacion_por_zona = {}
        for c in cuentas_con_consumo:
            zona = c["zona"]
            consumo = c["consumo_m3"]
            tarifa = tarifa_categoria(c["categoria"], c["subcategoria"])
            monto_facturado = consumo * tarifa
            
            if zona not in facturacion_por_zona:
                facturacion_por_zona[zona] = {
                    "monto_total": 0.0,
                    "consumo_total": 0.0,
                    "cuentas_afectadas": 0
                }
            
            facturacion_por_zona[zona]["monto_total"] += monto_facturado
            facturacion_por_zona[zona]["consumo_total"] += consumo
            facturacion_por_zona[zona]["cuentas_afectadas"] += 1
            
        # Ordenamos las zonas de forma descendente por el monto total facturado
        zonas_ordenadas = sorted(
            facturacion_por_zona.items(), 
            key=lambda x: x[1]["monto_total"], 
            reverse=True
        )
        
        # Tomamos el top 3
        top_3 = zonas_ordenadas[:3]
        
        print("\n=== TOP 3 ZONAS CON MAYOR DEUDA/FACTURACIÓN SIMULADA EN DISTRITO 5 ===")
        print(f"{'Posición':<10} | {'Zona':<25} | {'Monto Total (Bs)':<20} | {'Consumo (m³)':<15} | {'Cuentas Morosas':<15}")
        print("-" * 92)
        
        for idx, (zona, datos) in enumerate(top_3, start=1):
            monto = f"Bs {datos['monto_total']:,.2f}"
            consumo = f"{datos['consumo_total']:,.2f} m³"
            print(f"Top {idx:<5} | {zona:<25} | {monto:<20} | {consumo:<15} | {datos['cuentas_afectadas']:<15}")
        print("-" * 92)
        
        cluster.shutdown()
        
    except Exception as e:
        print(f"Error general en la consulta 2: {e}")

if __name__ == "__main__":
    main()
