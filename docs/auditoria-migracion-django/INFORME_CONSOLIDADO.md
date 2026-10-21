# Informe Consolidado de Auditoría Técnica, Funcional y Estrategia de Migración
## Sistema de Gestión Comercial - JC Distribuciones

---

## 1. Resumen Ejecutivo
El presente documento constituye el **Informe Consolidado Final** de la auditoría técnica y funcional realizada sobre el ecosistema de software y bases de datos de **JC Distribuciones**. Este informe sintetiza los hallazgos del análisis de la solución .NET de desarrollo (`CursoSistemaVenta.sln`) y de la base de datos SQL Server real en producción (`script sp produccion.sql`), estableciendo las bases conceptuales, arquitectónicas y la estrategia ETL para la futura implementación del sistema en **Django (Python)** y **PostgreSQL**.

---

## 2. Alcance Analizado
La auditoría cubrió la totalidad del código fuente, proyectos Visual Studio, scripts de base de datos y archivos de documentación existentes en el espacio de trabajo:
- Solución .NET de desarrollo en C# WinForms (.NET Framework 4.7.2).
- Intentos de modernización a .NET 8 y microservicio de integración AFIP (`src/`).
- Base de datos SQL Server de producción real (56 tablas, 130 procedimientos almacenados).
- Reglas de formación de precios, cálculos de IVA, comprobantes fiscales, devoluciones y stock.

---

## 3. Fuentes Inspeccionadas
- **Repositorio de Desarrollo**: `c:\jcdistribuciones\jcdistribuciones\`
  - `CursoSistemaVenta.sln` y proyectos `CapaPresentacion`, `CapaNegocio`, `CapaDatos`, `CapaEntidad`, `QuerySQL`.
  - `src/SistemaVentas.sln` y `src/webafip/AfipApi.sln`.
- **Script SQL de Producción**: `c:\jcdistribuciones\script sp produccion.sql` (627 KB, UTF-16LE).

---

## 4. Arquitectura del Desarrollo .NET
El proyecto de desarrollo implementa un patrón estricto de **Arquitectura en N-Capas (N-Tier)**:
- `CapaPresentacion`: WinForms UI con menús dinámicos basada en roles, grillas avanzadas y generador de tickets HTML/PDF (`GeneradorComprobantes.cs`).
- `CapaNegocio`: Encapsulamiento de reglas comerciales, validaciones de CUIT/DNI, extensión partial class para Notas de Crédito (`CN_Venta_Extensiones.cs`) y calculadora de listas de precios (`CN_Lista.cs`).
- `CapaDatos`: ADO.NET optimizado con paso de parámetros complejos en Table-Valued Parameters (`EDetalle_Venta`, `EDetalle_Compra`).
- `CapaEntidad`: DTOs/POCOs compartidos entre capas.

---

## 5. Inventario de Módulos
- **Módulos Implementados en Desarrollo**: Usuarios, Clientes, Proveedores, Productos, Categorías, Listas de Precios, Compras, Ventas Fiscales (FA, FB, Recibos, Remitos), Devoluciones / NC (NCA, NCB), Reportes con exportación Excel.
- **Módulos Críticos Exclusivos de Producción**: Pedidos Pre-Venta, Cuenta Corriente de Clientes, Arqueo de Caja Diaria, Vendedores y Rutas por Zonas.

---

## 6. Procesos Comerciales
Reconstrucción de los flujos operativos clave:
1. **Formación de Lista de Precios**: $\text{Costo} \rightarrow \text{Recargo} \rightarrow \text{IVA} \rightarrow \text{Descuento}$.
2. **Emisión de Venta Fiscal**: Selección de TipoComprobante $\rightarrow$ Escáner de Código de Barras $\rightarrow$ Discriminación de IVA según `DiscriminaIVA` $\rightarrow$ Inserción Transaccional `usp_RegistrarVenta` $\rightarrow$ Impresión Ticket/HTML.
3. **Devolución / Nota de Crédito**: Búsqueda del comprobante original $\rightarrow$ Validación de cantidades $\le$ originales $\rightarrow$ Generación de NCA/NCB $\rightarrow$ Restitución de stock.

---

## 7. Modelo de Datos Deducido del Desarrollo
Esquema relacional compuesto por 15 tablas principales (`USUARIO`, `ROL`, `PERMISO`, `CLIENTE`, `PROVEEDOR`, `CATEGORIA`, `PRODUCTO`, `IVA`, `Lista`, `COMPRA`, `DETALLE_COMPRA`, `VENTA`, `DETALLE_VENTA`, `TipoComprobante`, `NEGOCIO`).

---

## 8. Modelo Productivo SQL Server
Análisis del DDL de producción de 56 tablas y 130 Stored Procedures. Destaca la presencia de **tablas clonadas/versionadas** (`articulo1`, `comprobante2`), **ausencia de claves foráneas declaradas**, e importes en `DECIMAL(6,2)` vulnerables a desbordamiento numérico.

---

## 9. Reglas de Precios, Descuentos e IVA
- **Fórmula de Precio Venta**:
  $$ P_{\text{final}} = \text{Math.Round}\left(\left[\left(P_{\text{costo}} \cdot (1 + \frac{R}{100})\right) \cdot (1 + \frac{IVA}{100})\right] \cdot (1 - \frac{Desc}{100}), 2\right) $$
- **IVA Discriminado**: Factura A exige discriminar IVA al 21%. Factura B incluye el IVA en el precio unitario.

---

## 10. Remitos, Facturas, NC y NCF
- Las Notas de Crédito (NCA/NCB) ajustan el crédito del cliente y restituyen existencias al stock.
- En producción existen Notas de Crédito por Faltantes (NCF) para corregir diferencias de carga/despacho.

---

## 11. Control de Stock
- Actualización automática de existencias: Compras (+), Ventas (- si `ControlaStock=1`), Devoluciones (+).
- Evaluación continua de la condición de reposición: $\text{Stock} \le \text{Punto\_reposicion}$.

---

## 12. Roles y Permisos
- `ROL` (ADMINISTRADOR, EMPLEADO) asociado dinámicamente a `PERMISO.NombreMenu`.

---

## 13. Integraciones
- Microservicio en `src/webafip` con modelos y servicios mockeados para integración futura con Web Services de la AFIP (WSFEv1).

---

## 14. Comparación Desarrollo vs Producción
Discrepancia estructural crítica: Desarrollo es un POS genérico de mostrador; Producción es un sistema de distribución mayorista con Cta Cte, Pedidos y Caja.

---

## 15. Información Migrable Directamente
Proveedores, Vendedores, Catálogos de Geografía (Países, Provincias, Localidades, Zonas) y Condiciones de IVA.

---

## 16. Información que Requiere Transformación (ETL)
Artículos (`articulo` + `articulo1` + `articulo2`), Clientes (`cliente` + `cliente2`), Comprobantes (`comprobante` + `comprobante1` + `comprobante2` + `comprobante_anterior`) y Listas de Precios.

---

## 17. Brechas Funcionales
Ausencia en el desarrollo .NET de los módulos de Pedidos, Cta. Cte. y Caja Diaria.

---

## 18. Riesgos Técnicos y de Negocio
- Vulnerabilidad por contraseñas en texto plano.
- Riesgo de overflow monetario por `DECIMAL(6,2)` en producción.
- Inexistencia de cerrojos de concurrencia en ventas.

---

## 19. Propuesta Preliminar para Django / PostgreSQL
Mapeo de tipos de datos (`DECIMAL(14,2)`, `TIMESTAMPTZ`), división en Apps interconectadas (`usuarios`, `geografia`, `clientes`, `productos`, `pedidos`, `ventas`, `stock`, `cuentacorriente`) y uso de `citext` / `pg_trgm` para búsquedas eficientes.

---

## 20. Estrategia de Migración
Plan ETL automatizado en 18 pasos con tablas de correspondencia de IDs, saneamiento de huérfanos, validación monetaria y ventana de congelamiento de producción de 2 horas.

---

## 21. Orden Recomendado de Implementación
1. Core de Usuarios, Roles, Autenticación y Geografía.
2. Catálogo de Productos y Listas de Precios.
3. Portal de Clientes y Módulo de Pedidos Pre-Venta.
4. Facturación, Remitos y Gestión de Stock.
5. Devoluciones, Notas de Crédito y Cta. Cte.
6. Integración AFIP / ARCA asíncrona.

---

## 22. Preguntas Pendientes
Definir políticas de blanqueo de contraseñas, unificación de tablas clonadas, momento exacto de descuento de stock y facturación local sin AFIP en fase inicial.

---

## 23. Conclusión
El análisis realizado confirma que el sistema Django/PostgreSQL debe tomar como **fuente única de verdad para el modelo de datos y la migración histórica la base de datos de PRODUCCIÓN**, integrando la calculadora de precios y las mejoras de interfaz del proyecto de desarrollo.

---

## 24. Anexos y Referencias a Documentos Detallados

- [00_resumen_ejecutivo.md](file:///c:/jcdistribuciones/docs/auditoria-migracion-django/00_resumen_ejecutivo.md)
- [01_inventario_tecnico_net.md](file:///c:/jcdistribuciones/docs/auditoria-migracion-django/01_inventario_tecnico_net.md)
- [02_modulos_y_flujos.md](file:///c:/jcdistribuciones/docs/auditoria-migracion-django/02_modulos_y_flujos.md)
- [03_modelo_datos_desarrollo.md](file:///c:/jcdistribuciones/docs/auditoria-migracion-django/03_modelo_datos_desarrollo.md)
- [04_modelo_sqlserver_produccion.md](file:///c:/jcdistribuciones/docs/auditoria-migracion-django/04_modelo_sqlserver_produccion.md)
- [05_reglas_calculos_y_stock.md](file:///c:/jcdistribuciones/docs/auditoria-migracion-django/05_reglas_calculos_y_stock.md)
- [06_matriz_desarrollo_vs_produccion.md](file:///c:/jcdistribuciones/docs/auditoria-migracion-django/06_matriz_desarrollo_vs_produccion.md)
- [07_brechas_riesgos_y_deuda_tecnica.md](file:///c:/jcdistribuciones/docs/auditoria-migracion-django/07_brechas_riesgos_y_deuda_tecnica.md)
- [08_propuesta_modelo_django_postgresql.md](file:///c:/jcdistribuciones/docs/auditoria-migracion-django/08_propuesta_modelo_django_postgresql.md)
- [09_estrategia_migracion_historica.md](file:///c:/jcdistribuciones/docs/auditoria-migracion-django/09_estrategia_migracion_historica.md)
- [10_preguntas_y_decisiones_pendientes.md](file:///c:/jcdistribuciones/docs/auditoria-migracion-django/10_preguntas_y_decisiones_pendientes.md)
