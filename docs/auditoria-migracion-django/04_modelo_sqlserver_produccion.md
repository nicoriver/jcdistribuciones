# 04. Análisis y Diccionario de la Base de Datos SQL Server de Producción
## Inspección Completa de la Base de Datos Real (`jcdistribuciones`)

---

## 1. Inventario General de Objetos en Producción

El análisis del script de producción real (`c:\jcdistribuciones\script sp produccion.sql`, 627 KB, UTF-16LE) reveló la existencia de **186 Objetos SQL Server nativos**:

| Tipo de Objeto SQL | Cantidad Encontrada | Observaciones y Ejemplos Clave |
| :--- | :--- | :--- |
| **Tablas (`CREATE TABLE`)** | **56** | Incluye tablas operativas, catálogos, tablas clonadas (`articulo1`, `comprobante2`) y temporales. |
| **Procedimientos Almacenados (`CREATE PROCEDURE`)**| **130** | Stored Procedures divididos en convenciones `PA_INS_*` (17), `PA_SEL_*` (103) y `PA_UPD_*` (10). |
| **Vistas (`CREATE VIEW`)** | **0** | No se encontraron vistas declaradas explícitamente en el script DDL. |
| **Funciones User-Defined (`CREATE FUNCTION`)**| **0** | Toda la lógica de cálculo está embebida en Stored Procedures o en el cliente. |
| **Triggers (`CREATE TRIGGER`)** | **0** | No existen desencadenadores automáticos en la base de datos de producción. |
| **Tipos Definidos por Usuario (`CREATE TYPE`)**| **0** | En producción no se utilizan TVPs (Table-Valued Parameters). |

---

## 2. Diccionario de Tablas Críticas de Producción

### 2.1 Tabla: `articulo` (Maestro Principal de Artículos)
- **Registros/Uso**: Catálogo principal de productos en producción.

| Campo | Tipo SQL Server | Nulo | Clave | Valor predeterminado | Referencia | Uso probable | Observaciones |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `Id_articulo` | `INT` | NO | PK | `IDENTITY(1,1)` | Clave Primaria | Identificador único del producto | Auto-incremental |
| `Cod_articulo` | `VARCHAR(25)` | NO | - | Ninguno | Ninguna | Código de artículo | Clave de búsqueda comercial |
| `Descripcion` | `VARCHAR(50)` | NO | - | Ninguno | Ninguna | Nombre/Descripción | Longitud acotada (50 chars) |
| `Comentario` | `VARCHAR(250)`| NO | - | Ninguno | Ninguna | Detalles del producto | Texto descriptivo extendido |
| `Rubro` | `INT` | NO | FK (Imp)| Ninguno | `rubro(id_Rubro)` | Categoría / Rubro | Sin FK declarada en script |
| `Proveedor` | `INT` | NO | FK (Imp)| Ninguno | `proveedor(Id_proveedor)`| Proveedor principal | Sin FK declarada en script |
| `Codigo_de_barra`|`VARCHAR(25)` | NO | - | Ninguno | Ninguna | Código de barras escáner | Utilizado en POS |
| `Iva` | `DECIMAL(6,2)` | NO | - | Ninguno | Ninguna | Alícuota de IVA | **Riesgo**: `DECIMAL(6,2)` acotado |
| `Costo` | `DECIMAL(6,2)` | NO | - | Ninguno | Ninguna | Costo de compra | **Riesgo**: Máximo $9.999,99 |
| `Cantidad` | `INT` | NO | - | Ninguno | Ninguna | Stock físico | Existencia actual |
| `Punto_reposicion`|`INT` | NO | - | Ninguno | Ninguna | Umbral de reposición | Alerta de stock mínimo |
| `Descuento_Distri`|`DECIMAL(6,2)`| SI | - | Ninguno | Ninguna | Descuento distribuidor | Bonificación |
| `Descuento` | `DECIMAL(6,2)` | SI | - | Ninguno | Ninguna | Descuento general | Bonificación artículo |
| `Estado` | `INT` | SI | - | Ninguno | Ninguna | Estado del artículo | `1=Activo, 0=Inactivo` |

---

### 2.2 Tabla: `cliente` (Maestro Principal de Clientes)
- **Registros/Uso**: Entidades compradoras y estado de cuenta comercial.

| Campo | Tipo SQL Server | Nulo | Clave | Valor predeterminado | Referencia | Uso probable | Observaciones |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `Id_cliente` | `INT` | NO | PK | `IDENTITY(1,1)` | Clave Primaria | Identificador de cliente | Auto-incremental |
| `Apellido` | `VARCHAR(45)` | NO | - | Ninguno | Ninguna | Apellido del cliente | Campo obligatorio |
| `Nombre` | `VARCHAR(45)` | NO | - | Ninguno | Ninguna | Nombre del cliente | Campo obligatorio |
| `Razon_Social` | `VARCHAR(50)` | NO | - | Ninguno | Ninguna | Razón Social | Campo obligatorio |
| `Domicilio` | `VARCHAR(50)` | SI | - | Ninguno | Ninguna | Dirección | Domicilio legal/comercial |
| `Dni` | `VARCHAR(50)` | SI | - | Ninguno | Ninguna | DNI | Documento de identidad |
| `id_Tipo_dni` | `INT` | SI | FK (Imp)| Ninguno | `tipo_dni` | Tipo de Documento | Sin FK formal |
| `Id_Codigo_Iva` | `INT` | SI | FK (Imp)| Ninguno | `codigo_iva` | Condición Fiscal IVA | Sin FK formal |
| `Cuit` | `VARCHAR(20)` | SI | - | Ninguno | Ninguna | CUIT | Identificador Tributario |
| `Id_Zona` | `INT` | SI | FK (Imp)| Ninguno | `zona` | Zona de reparto | Asignación de ruta |
| `Id_Localidad` | `INT` | SI | FK (Imp)| Ninguno | `localidad` | Ciudad / Localidad | Ubicación geográfica |
| `Id_Provincia` | `INT` | SI | FK (Imp)| Ninguno | `provincia` | Provincia | Ubicación geográfica |
| `Id_Pais` | `INT` | SI | FK (Imp)| Ninguno | `pais` | País | Ubicación geográfica |
| `Telefono` | `VARCHAR(45)` | SI | - | Ninguno | Ninguna | Teléfono fijo | Contacto |
| `Telefono_Alt` | `VARCHAR(45)` | SI | - | Ninguno | Ninguna | Teléfono celular | Contacto alternativo |
| `Fax` | `VARCHAR(45)` | SI | - | Ninguno | Ninguna | Fax | Inutilizado |
| `Email` | `VARCHAR(45)` | SI | - | Ninguno | Ninguna | Correo electrónico | Notificaciones |
| `Web` | `VARCHAR(45)` | SI | - | Ninguno | Ninguna | Sitio Web | Opcional |
| `Contacto` | `VARCHAR(45)` | SI | - | Ninguno | Ninguna | Persona de contacto | Nombre de contacto |
| `Id_vendedor` | `INT` | SI | FK (Imp)| Ninguno | `vendedor` | Vendedor asignado | Rauta de preventa |
| `Latitud` | `DECIMAL(10,8)`| SI | - | Ninguno | Ninguna | Latitud GPS | Geolocalización |
| `Longitug` | `DECIMAL(10,8)`| SI | - | Ninguno | Ninguna | Longitud GPS | Geolocalización |
| `Estado` | `INT` | SI | - | Ninguno | Ninguna | Estado del cliente | `1=Activo` |

---

### 2.3 Tabla: `comprobante` (Cabecera General de Ventas y Comprobantes)
- **Registros/Uso**: Emisión de Facturas, Recibos, Remitos y Notas de Crédito.

| Campo | Tipo SQL Server | Nulo | Clave | Valor predeterminado | Referencia | Uso probable | Observaciones |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `Id_Comprobante`| `INT` | NO | PK | `IDENTITY(1,1)` | Clave Primaria | Identificador único | Auto-incremental |
| `Fecha` | `DATETIME` | NO | - | Ninguno | Ninguna | Fecha de emisión | Timestamp |
| `Descripcion` | `VARCHAR(45)` | NO | - | Ninguno | Ninguna | Tipo Comprobante | Texto (ej: "Factura A") |
| `Domicilio` | `VARCHAR(45)` | NO | - | Ninguno | Ninguna | Domicilio fiscal | Copia histórica |
| `Condicion_iva` | `INT` | NO | - | Ninguno | Ninguna | Código IVA Cliente | Condición impositiva |
| `Cuit` | `VARCHAR(20)` | NO | - | Ninguno | Ninguna | CUIT del comprador | Copia histórica |
| `Forma_pago` | `INT` | NO | FK (Imp)| Ninguno | `forma_pago` | Condición de venta | `1=Contado, 2=CtaCte` |
| `Subtotal` | `DECIMAL(10,2)`| NO | - | Ninguno | Ninguna | Neto Gravado | Subtotal antes de IVA |
| `Iva_21` | `DECIMAL(10,2)`| NO | - | Ninguno | Ninguna | Importe IVA 21% | Discriminado |
| `Iva_10_5` | `DECIMAL(10,2)`| NO | - | Ninguno | Ninguna | Importe IVA 10.5% | Discriminado |
| `Total` | `DECIMAL(10,2)`| NO | - | Ninguno | Ninguna | Importe Total | Monto final factura |
| `id_cliente` | `INT` | NO | FK (Imp)| Ninguno | `cliente` | Cliente comprador | Clave foránea implícita |
| `nrocomprobante` | `VARCHAR(25)` | NO | - | Ninguno | Ninguna | Número impreso | Correlativo (0001-000123) |
| `id_vendedor` | `INT` | NO | FK (Imp)| Ninguno | `vendedor` | Vendedor emisor | Comisión / Ruta |
| `Estado` | `INT` | NO | - | Ninguno | Ninguna | Estado del comprobante| `1=Emitido, 0=Anulado` |
| `id_punto_de_venta`|`INT` | NO | FK (Imp)| Ninguno | `punto_de_venta` | Punto de Venta | Nro de Sucursal/Caja |
| `id_TipoComprobante`|`INT` | NO | FK (Imp)| Ninguno | `tipocomprobante` | Categoría Fiscal | `1=FA, 2=FB, 3=REC` |

---

### 2.4 Tabla: `detallecomprobante` (Renglones de Comprobantes)
- **Registros/Uso**: Detalle de artículos incluidos en cada comprobante emitido.

| Campo | Tipo SQL Server | Nulo | Clave | Valor predeterminado | Referencia | Uso probable | Observaciones |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `id_detallecomprobante`| `INT` | NO | PK | `IDENTITY(1,1)`| Clave Primaria | Identificador renglón | Auto-incremental |
| `id_comprobante` | `INT` | NO | FK (Imp)| Ninguno | `comprobante` | Comprobante Padre | FK Implícita |
| `id_articulo` | `INT` | NO | FK (Imp)| Ninguno | `articulo` | Artículo vendido | FK Implícita |
| `Cod_Articulo` | `VARCHAR(15)` | NO | - | Ninguno | Ninguna | Código de producto | Copia histórica |
| `Descripción` | `VARCHAR(45)` | NO | - | Ninguno | Ninguna | Nombre de producto | Copia histórica |
| `Cantidad` | `INT` | NO | - | Ninguno | Ninguna | Unidades vendidas | Cantidad entregada |
| `Precio_Unitario`| `DECIMAL(6,2)`| NO | - | Ninguno | Ninguna | Precio cobrado | **Riesgo**: `DECIMAL(6,2)` corto |
| `Descuento` | `DECIMAL(6,2)`| NO | - | Ninguno | Ninguna | Descuento aplicado | Bonificación renglón |
| `Importe` | `DECIMAL(6,2)`| NO | - | Ninguno | Ninguna | Subtotal renglón | **Riesgo**: `DECIMAL(6,2)` corto |
| `Iva` | `DECIMAL(6,2)`| NO | - | Ninguno | Ninguna | Alícuota IVA % | Impuesto |

---

## 3. Hallazgos Críticos y Deuda Técnica en la Base de Producción

1. **Tablas Clonadas / Versionadas sin Normalización**:
   - Existen las tablas: `articulo1`, `articulo2`, `cliente2`, `comprobante1`, `comprobante2`, `comprobante_anterior`, `detallecomprobante1`, `detallecomprobante2`, `detallecomprobante_ant`, `Lista1`, `Lista2`.
   - **Diagnóstico**: Estas tablas fueron creadas manualmente en producción para archivar periodos históricos o realizar ajustes masivos. Contienen datos transaccionales reales que deben ser consolidados mediante un script `UNION ALL` durante la migración a PostgreSQL.
2. **Inexistencia de Claves Foráneas Formales (`FOREIGN KEY`)**:
   - Ninguna de las 56 tablas de producción declara restricciones `CONSTRAINT FK_... FOREIGN KEY`.
   - **Diagnóstico**: La integridad referencial depende al 100% de la aplicación o de los Stored Procedures. Existen altas probabilidades de encontrar **registros huérfanos** en `detallecomprobante` o `comprobante`.
3. **Peligro de Desbordamiento Numérico (`DECIMAL(6,2)`)**:
   - Campos clave de precios e importes como `articulo.Costo`, `detallecomprobante.Precio_Unitario` e `Importe` están definidos como `DECIMAL(6,2)`.
   - **Diagnóstico**: El valor máximo permitido en `DECIMAL(6,2)` es **$ 9.999,99**. En el contexto inflacionario actual, cualquier producto de valor superior a $10.000 generará un error fatal de **Arithmetic Overflow Error** en SQL Server.
4. **Fechas Almacenadas en Formato Texto**:
   - Varios Stored Procedures reciben y convierten fechas usando `VARCHAR(10)` con formateo `103` (dd/mm/yyyy).
5. **Procedimientos Almacenados con Reglas de Negocio Complejas**:
   - Stored procedures como `PA_INS_Facturas`, `PA_INS_NotaCredito`, `PA_INS_Pedidos`, `PA_SEL_EstadisticaUtilidades` contienen lógica de descuento de stock, cálculo de comisiones e imputación de cuenta corriente que deberá ser migrada a servicios de dominio en Django.
