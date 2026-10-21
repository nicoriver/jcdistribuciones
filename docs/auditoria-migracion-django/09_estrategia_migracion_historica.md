# 09. Estrategia de Migración Histórica de Datos
## Plan ETL de Extracción, Transformación, Carga y Conciliación Financiera

---

## 1. Arquitectura y Metodología ETL (SQL Server $\rightarrow$ PostgreSQL)

La migración de los datos históricos desde la base de datos productiva SQL Server (`jcdistribuciones`) hacia la nueva base de datos PostgreSQL se ejecutará mediante un **Pipeline ETL automatizado en Python** (`sqlalchemy` + `psycopg2` + `pandas`), garantizando trazabilidad, idempotencia y capacidad de ensayo previo.

```mermaid
flowchart TD
    subgraph Origen - SQL Server Producción
        PROD_Tables[(56 Tablas: articulo, cliente, comprobante, etc.)]
    end

    subgraph Fase ETL (Script Python Migration Pipeline)
        F1[1. Extracción & Profiling UTF-16] --> F2[2. Normalización & Clean Data]
        F2 --> F3[3. Deduplicación & UNION ALL de Tablas Clonadas]
        F3 --> F4[4. Mapeo de IDs en Tabla de Correspondencia]
        F4 --> F5[5. Transformación a Esquema Django]
    end

    subgraph Destino - PostgreSQL Django DB
        PG_Tables[(Esquema Relacional PostgreSQL)]
        Audit_Logs[(Tablas de Auditoría y Conciliación)]
    end

    PROD_Tables --> F1
    F5 --> PG_Tables
    F5 --> Audit_Logs
```

---

## 2. Plan de Migración Histórica en 18 Pasos Estructurados

### Paso 1: Inventario y Perfilado de Datos (Data Profiling)
Ejecución de consultas de diagnóstico en SQL Server para contabilizar filas totales, rangos de fechas, nulos no esperados y caracteres corruptos.

### Paso 2: Extracción Segura en Modo Lectura (ReadOnly Extraction)
Exportación de las 56 tablas de producción a archivos intermediarios formateados (`Parquet` / `CSV UTF-8`), utilizando copias estáticas o snapshots para no bloquear la operación diaria.

### Paso 3: Normalización de Codificación y Limpieza de Caracteres
Conversión de cadenas codificadas en `UTF-16LE` / `latin1` a `UTF-8` limpio, eliminando caracteres nulos `0x00`, espacios al final (`RTRIM`) y tabulaciones.

### Paso 4: Consolidación y Deduplicación de Tablas Fragmentadas
Ejecución de sentencias `UNION ALL` para unificar tablas duplicadas:
- `articulo` + `articulo1` + `articulo2` $\rightarrow$ `staging_articulo`
- `cliente` + `cliente2` $\rightarrow$ `staging_cliente`
- `comprobante` + `comprobante1` + `comprobante2` + `comprobante_anterior` $\rightarrow$ `staging_comprobante`
- `detallecomprobante` + `detallecomprobante1` + `detallecomprobante2` + `detallecomprobante_ant` $\rightarrow$ `staging_detalle`

### Paso 5: Construcción de Tablas de Correspondencia de Identificadores (ID Mapping)
Creación de tablas intermedias de mapeo (`map_cliente_ids`, `map_articulo_ids`, `map_comprobante_ids`) para conservar la trazabilidad de las claves primarias legadas:

| Tabla Mapeo | `id_legacy_sqlserver` | `tabla_origen` | `id_nuevo_postgresql` |
| :--- | :--- | :--- | :--- |
| `map_articulo_ids` | `105` | `articulo1` | `105` |
| `map_comprobante_ids`| `4502` | `comprobante2` | `4502` |

### Paso 6: Transformación de Estructuras y Tipos de Datos
Casting explícito de tipos monetarios `DECIMAL(6,2)` a `NUMERIC(14,2)` y formateo de fechas `VARCHAR` a `TIMESTAMPTZ` ISO 8601.

### Paso 7: Saneamiento de Referencias Huérfanas y Integridad Referencial
Identificación de renglones en `detallecomprobante` cuyo `id_comprobante` o `id_articulo` no existe en las tablas padres. Asignación automática a registros genéricos de respaldo (`ARTÍCULO DESCONTINUADO GENÉRICO`, `CLIENTE OCASIONAL`).

### Paso 8: Carga Inicial de Catálogos y Geografía
Inserción en PostgreSQL de los modelos independientes: Países, Provincias, Localidades, Zonas, Alícuotas de IVA y Proveedores.

### Paso 9: Carga de Clientes y Vendedores
Inserción de la tabla consolidada de clientes, asociando sus claves foráneas a geografía y vendedores asignados.

### Paso 10: Carga del Maestro de Artículos y Listas de Precios
Inserción de artículos en `productos_producto` y generación de sus correspondientes registros de precios en `productos_precioproducto`.

### Paso 11: Carga Transaccional de Comprobantes (Ventas, Remitos, NC)
Carga masiva por lotes (Batch Insertion de 5,000 registros) en `ventas_comprobante` desactivando temporalmente los triggers de auditoría para maximizar velocidad.

### Paso 12: Carga de Renglones de Detalle (`ventas_detallecomprobante`)
Inserción de los renglones de detalle en PostgreSQL enlazados con las claves mapeadas en el Paso 5.

### Paso 13: Carga del Histórico de Cuenta Corriente y Pedidos
Carga del módulo de pedidos (`pedido`, `detallepedido`) y movimientos de cuenta corriente (`MovimientoCtaCte`).

### Paso 14: Restablecimiento de Secuencias (`SETVAL`)
Actualización de los contadores `BIGSERIAL` en PostgreSQL al valor máximo de los IDs importados:
```sql
SELECT setval('ventas_comprobante_id_seq', (SELECT MAX(id) FROM ventas_comprobante));
```

### Paso 15: Conciliación Monetaria y Cuadre de Cantidades (Automated Audit)
Ejecución del script automático de verificación para comparar totales monetarios y unidades entre SQL Server y PostgreSQL.

### Paso 16: Ensayos de Migración en Ambiente de Staging (Dry-Runs)
Realización de al menos 3 ensayos completos de migración en un servidor de pruebas midiendo tiempos de ejecución y ajustando scripts.

### Paso 17: Congelamiento de Producción (Cutover Window)
Detención de la aplicación desktop actual, respaldo final de SQL Server y ventana de migración definitiva (estimada en 2 horas).

### Paso 18: Validación Posterior y Puesta en Marcha (Go-Live)
Verificación por parte del equipo contable/operativo y habilitación del nuevo sistema Django.

---

## 3. Guion de Script de Conciliación Automática (SQL Verification)

Consultas automáticas para validar la fidelidad del proceso ETL:

```sql
-- 1. Verificación de Cantidad de Registros por Tabla
SELECT 'Clientes' AS Entidad, (SELECT COUNT(*) FROM cliente) AS SQLServer, (SELECT COUNT(*) FROM clientes_cliente) AS PostgreSQL
UNION ALL
SELECT 'Artículos', (SELECT COUNT(*) FROM articulo), (SELECT COUNT(*) FROM productos_producto)
UNION ALL
SELECT 'Comprobantes', (SELECT COUNT(*) FROM comprobante), (SELECT COUNT(*) FROM ventas_comprobante);

-- 2. Conciliación Monetaria Mensual de Ventas
SELECT 
    DATETRUNC('month', fecha_emision) AS Mes,
    SUM(monto_total) AS TotalVentasPG
FROM ventas_comprobante
GROUP BY 1
ORDER BY 1;
```

---

## 4. Plan de Reversión (Rollback Strategy)

Si durante la ventana de migración definitiva se detecta una falla crítica no subsanable en un plazo de 60 minutos:
1. Re-habilitar inmediatamente los accesos a la aplicación .NET desktop en producción.
2. La base de datos SQL Server de producción permanece **intacta y sin modificaciones**, ya que el proceso ETL opera exclusivamente en modo lectura.
3. Descartar la base PostgreSQL de staging y registrar el incidente para su corrección.
