# Verificar Datos Reales en el Mapa de Calor

## ¿Cómo funciona el mapa de calor ODS 6?

### Fórmula:
```
Consumo Promedio = Consumo Total (m³) / Total de Cuentas
```

### Clasificación (Semáforo ODS 6):

| Rango | Color | Clasificación | Significado |
|-------|-------|---------------|------------|
| < 10 m³/mes | 🔴 Rojo Oscuro | Alerta - Escasez | Posible brecha de acceso, baja presión, cortes o falta de red |
| 10-20 m³/mes | 🟢 Verde | Sostenible | Consumo eficiente y sostenible |
| 20-30 m³/mes | 🟡 Amarillo | Normal Alto | Consumo aceptable con vigilancia |
| 30-45 m³/mes | 🟠 Naranja | Sobreconsumo | Consumo elevado, posible derroche o fuga |
| > 45 m³/mes | 🔴 Rojo | Crítico | Estrés hídrico crítico, prioridad de inspección |

## ¿Cómo ver tus datos reales?

### Opción 1: Ejecutar script de verificación
```bash
cd d:\practica5-semapa-cassandra
python check_real_data.py
```

Esto mostrará:
- Consumo total por distrito
- Total de cuentas
- Consumo promedio calculado
- Clasificación automática según ODS 6

### Opción 2: Consultar Cassandra directamente
```bash
cqlsh
USE semapa;
SELECT distrito, periodo, consumo_m3, total_cuentas 
FROM consumo_distrito_mes 
LIMIT 20;
```

### Opción 3: Ver en el dashboard
1. Abre http://localhost:3000
2. Ve a Dashboard Alcaldía
3. Busca la tabla "Semáforo ODS ciudadano - consumo diario por persona"
4. Haz click en los círculos del mapa para ver popups detallados

## ¿Qué datos estoy viendo?

Tu mapa ahora muestra:
- **Tamaño del círculo**: Proporcional a la prioridad (más grande = más crítico)
- **Color**: Basado en consumo promedio por cuenta
- **Popup**: Información detallada al hacer click

## Próximos pasos para datos más reales:

1. Verifica que `load_data.py` esté cargando correctamente desde tus CSV
2. Si ves todos los distritos en verde, puede ser que:
   - Los datos de lecturas (lecturas.csv) sean antiguos o no representativos
   - Las cuentas y medidores no están bien vinculados
   - Necesitas cargar nuevos datos

3. Para recargar datos:
```bash
cd d:\practica5-semapa-cassandra
python app/load_data.py
```
