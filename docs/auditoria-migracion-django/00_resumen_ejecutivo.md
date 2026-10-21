# 00. Resumen Ejecutivo
## Auditoría Técnica, Funcional y Diagnóstico de Migración - JC Distribuciones

---

## 1. Presentación y Propósito
El presente informe documenta los resultados de la **auditoría técnica y funcional exhaustiva** realizada sobre la solución de software y bases de datos de **JC Distribuciones**. El objetivo central de este estudio es proporcionar un diagnóstico fidedigno y riguroso para fundamentar la futura reconstrucción e implementación de un sistema web integral sobre **Django (Python)** y **PostgreSQL**, así como definir una estrategia de **migración histórica de datos** libre de pérdidas y riesgos operativos.

---

## 2. Alcance y Elementos Analizados
La auditoría abarcó la totalidad de los repositorios y archivos asignados:
1. **Proyecto .NET de Desarrollo (`c:\jcdistribuciones\jcdistribuciones`)**:
   - Solución `.NET Framework 4.7.2` (`CursoSistemaVenta.sln`) compuesta por 5 proyectos principales: `CapaPresentacion` (WinForms), `CapaNegocio`, `CapaDatos`, `CapaEntidad` y `QuerySQL`.
   - Módulos adicionales en desarrollo (`src/`): migración inicial a `.NET 8` / `NetStandard` (`SistemaVentas.sln`) y microservicio de facturación electrónica AFIP (`AfipApi.sln`).
   - Scripts SQL de desarrollo (`QuerySQL/*.sql`, `src/SQL/*.sql`).
2. **Script SQL Server de Producción (`c:\jcdistribuciones\script sp produccion.sql`)**:
   - Script DDL/DML real de la base de datos productiva (`jcdistribuciones`) de 627 KB (Codificación UTF-16LE).
   - Consta de **56 tablas**, **130 procedimientos almacenados** (`PA_INS_*`, `PA_SEL_*`, `PA_UPD_*`), catálogos y tipos de datos nativos.

---

## 3. Principales Hallazgos y Diagnóstico

### 3.1 Divergencia Estructural Crítica entre Producción y Desarrollo
Existe una **discrepancia fundamental de modelo de datos** entre el sistema real en producción y el desarrollo .NET analizado:
- **Producción** gestiona un flujo centrado en **Pedidos de Venta**, **Comprobantes**, **Cta. Cte. de Clientes**, **Caja Diaria**, **Vendedores** y **Múltiples Tablas Fragmentadas / Clonadas** (`articulo`, `articulo1`, `articulo2`, `cliente`, `cliente2`, `comprobante`, `comprobante1`, `comprobante2`, `comprobante_anterior`, `detallecomprobante1`, etc.).
- **Desarrollo** fue construido sobre una plantilla/modelo genérico N-Capas (`DBVENTASDEMO`) enfocado en **Ventas Directas de Mostrador**, **Compras a Proveedores** y **Control de Stock Básico**, omitiendo por completo los módulos productivos de Cta. Cte., Pedidos, Caja, Vendedores y la estructura histórica real.

### 3.2 Implicancia para el Futuro Sistema Django
- **El desarrollo .NET NO es un sustituto válido del modelo de datos de producción**, sino una referencia parcial de la interfaz de ventas de mostrador y calculadora de listas de precios.
- **La fuente primaria para el modelo conceptual de Django y la migración histórica de datos DEBE SER la base de datos de PRODUCCIÓN (`script sp produccion.sql`)**, integrada con los requerimientos futuros del negocio (Portal de Clientes, Aprobación de Pedidos, Descuentos por Vendedor y Distribución por Zonas).

---

## 4. Clasificación General de Evidencia por Módulo

| Módulo | Clasificación | Evidencia Clave en Código / SQL | Estado Diagnóstico |
| :--- | :--- | :--- | :--- |
| **Autenticación y Permisos** | **CONFIRMADO / PARCIAL** | `Login.cs:L30`, `Inicio.cs:L45`, `PERMISO`, `regusuarios` | Funcional en desarrollo (Menú por Rol). Clave en texto plano (Requiere Hash SHA256/BCrypt). |
| **Clientes y Vendedores** | **CONFIRMADO** | `frmClientes.cs`, `cliente` (BD Prod), `vendedor` (BD Prod) | Producción posee datos extendidos de Cta Cte y Vendedor asignado. |
| **Artículos y Listas de Precios** | **CONFIRMADO** | `frmProducto.cs`, `CN_Lista.cs:L44`, `articulo`, `Lista` | Desarrollo agrega calculadora dinámica (Costo + Utilidad + IVA - Desc). |
| **Pedidos y Pre-Venta** | **CONFIRMADO (PROD) / NO IMPL (DEV)**| `pedido`, `detallepedido`, `tmp_pedido`, `PA_INS_Pedidos` | Implementado en BD Producción; Ausente en proyecto .NET desarrollo. |
| **Ventas Fiscales y Remitos** | **CONFIRMADO** | `frmVentasFiscales.cs:L225`, `comprobante`, `VENTA` | Desarrollo soporta FA, FB, Recibos y Remitos con discriminación de IVA. |
| **Devoluciones y NC** | **CONFIRMADO** | `frmDevoluciones.cs`, `CN_Venta_Extensiones.cs`, `PA_INS_NotaCredito` | Generación de NCA / NCB con restitución de existencias a stock. |
| **Cuenta Corriente y Caja** | **CONFIRMADO (PROD) / NO IMPL (DEV)**| `MovimientoCtaCte`, `caja`, `PA_INS_MovimientoCtaCte` | Crítico en Producción; Ausente en desarrollo .NET. |
| **Integración AFIP / ARCA** | **PARCIAL / DOCUMENTADO** | `src/webafip/AfipApi`, `Costo terminado con iva.docx` | Microservicio simulado en desarrollo; ausente en backend principal. |

---

## 5. Resumen de Brechas y Riesgos de Migración

1. **Riesgo de Pérdida de Histórico por Tablas Clonadas en Producción**: Tablas como `comprobante1`, `comprobante2` y `articulo1` contienen transacciones históricas no consolidadas. Se requiere una fase de *Union & Deduplication* previa al ETL hacia PostgreSQL.
2. **Riesgo Monetario por Decimales Fraccionados**: Campos de importes en producción definidos como `DECIMAL(6,2)` o `DECIMAL(10,0)` amenazan con desbordamiento (Overflow Error) ante montos superiores a $9.999,99. Django debe implementar `DecimalField(max_digits=14, decimal_places=2)`.
3. **Inconsistencia de Fechas y Textos Libres**: Fechas guardadas como `VARCHAR` en SPs legados y codificación `latin1`/`UTF-16` requieren limpieza y conversión a `TIMESTAMPTZ` en PostgreSQL.
4. **Ausencia de Control de Concurrencia**: Ni desarrollo ni producción utilizan cerrojos atómicos o transacciones pesimistas al modificar existencias de productos.

---

## 6. Navegación del Informe y Estructura de Documentos

El informe completo de auditoría está organizado de forma modular en los siguientes entregables:

- [00_resumen_ejecutivo.md](file:///c:/jcdistribuciones/docs/auditoria-migracion-django/00_resumen_ejecutivo.md): Resumen de alto nivel y diagnóstico del proyecto.
- [01_inventario_tecnico_net.md](file:///c:/jcdistribuciones/docs/auditoria-migracion-django/01_inventario_tecnico_net.md): Inventario completo de archivos, proyectos, dependencias y evidencia C#.
- [02_modulos_y_flujos.md](file:///c:/jcdistribuciones/docs/auditoria-migracion-django/02_modulos_y_flujos.md): Reconstrucción funcional de procesos de negocio, pantallas y flujos.
- [03_modelo_datos_desarrollo.md](file:///c:/jcdistribuciones/docs/auditoria-migracion-django/03_modelo_datos_desarrollo.md): Modelo de datos deducido de la solución .NET de desarrollo.
- [04_modelo_sqlserver_produccion.md](file:///c:/jcdistribuciones/docs/auditoria-migracion-django/04_modelo_sqlserver_produccion.md): Diccionario completo de 56 tablas y 130 SPs de la BD productiva.
- [05_reglas_calculos_y_stock.md](file:///c:/jcdistribuciones/docs/auditoria-migracion-django/05_reglas_calculos_y_stock.md): Fórmulas matemáticas, formación de precios, IVA, NC y reglas de stock.
- [06_matriz_desarrollo_vs_produccion.md](file:///c:/jcdistribuciones/docs/auditoria-migracion-django/06_matriz_desarrollo_vs_produccion.md): Matriz de correspondencia entidad por entidad y nivel de coincidencia.
- [07_brechas_riesgos_y_deuda_tecnica.md](file:///c:/jcdistribuciones/docs/auditoria-migracion-django/07_brechas_riesgos_y_deuda_tecnica.md): Auditoría de seguridad, deuda técnica, concurrencia e inconsistencias.
- [08_propuesta_modelo_django_postgresql.md](file:///c:/jcdistribuciones/docs/auditoria-migracion-django/08_propuesta_modelo_django_postgresql.md): Especificación de arquitectura Django, modelos ORM, conversión de tipos SQL y servicios.
- [09_estrategia_migracion_historica.md](file:///c:/jcdistribuciones/docs/auditoria-migracion-django/09_estrategia_migracion_historica.md): Plan de ETL en 18 pasos, conciliación monetaria y scripts de verificación.
- [10_preguntas_y_decisiones_pendientes.md](file:///c:/jcdistribuciones/docs/auditoria-migracion-django/10_preguntas_y_decisiones_pendientes.md): Cuestionario técnico-operativo bloqueante para el equipo directivo.
- [INFORME_CONSOLIDADO.md](file:///c:/jcdistribuciones/docs/auditoria-migracion-django/INFORME_CONSOLIDADO.md): Informe final unificado de lectura independiente.
