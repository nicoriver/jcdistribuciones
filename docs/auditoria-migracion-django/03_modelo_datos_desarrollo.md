# 03. Modelo de Datos Deducido del Proyecto de Desarrollo
## Análisis del Esquema Relacional .NET (`DBVENTASDEMO`)

---

## 1. Introducción
El proyecto .NET de desarrollo utiliza una estructura relacional en SQL Server denominada conceptualmente `DBVENTASDEMO`. Este esquema fue deducido mediante la inspección cruzada de los scripts DDL/DML (`QuerySQL/*.sql`), las clases entidad (`CapaEntidad/*.cs`), el código de acceso a datos (`CapaDatos/*.cs`) y las grillas de formularios WinForms (`CapaPresentacion`).

---

## 2. Diagrama Entidad-Relación Deducido del Desarrollo

```mermaid
erdiagram
    ROL ||--o{ PERMISO : "1:N (Tiene)"
    ROL ||--o{ USUARIO : "1:N (Asignado)"
    USUARIO ||--o{ VENTA : "1:N (Registra)"
    USUARIO ||--o{ COMPRA : "1:N (Registra)"
    PROVEEDOR ||--o{ COMPRA : "1:N (Suministra)"
    COMPRA ||--|{ DETALLE_COMPRA : "1:N (Contiene)"
    PRODUCTO ||--|{ DETALLE_COMPRA : "1:N (Comprado)"
    CATEGORIA ||--o{ PRODUCTO : "1:N (Clasifica)"
    PRODUCTO ||--|{ DETALLE_VENTA : "1:N (Vendido)"
    VENTA ||--|{ DETALLE_VENTA : "1:N (Contiene)"
    CLIENTE ||--o{ VENTA : "1:N (Compra)"
    TipoComprobante ||--o{ VENTA : "1:N (Tipifica)"
    PRODUCTO ||--o{ Lista : "1:N (Precios)"
    IVA ||--o{ Lista : "1:N (Alícuota)"
```

---

## 3. Catálogo Detallado de Tablas Deducidas

### 3.1 Tabla: `USUARIO`
- **Finalidad**: Almacenar credenciales de operadores del sistema y su asociación a un rol.
- **Evidencia**: `QueryResumen.txt:L49`, `Usuario.cs`, `CD_Usuario.cs`.
- **Certeza**: **CONFIRMADO**.

| Campo | Tipo SQL Deducido | Nulo | Clave | Valor Predeterminado | Referencia / Restricción | Certeza | Evidencia |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `IdUsuario` | `INT` | NO | PK (IDENTITY) | `IDENTITY(1,1)` | Clave Primaria | CONFIRMADO | `QueryResumen.txt:L50` |
| `Documento` | `VARCHAR(50)` | NO | UNIQUE | Ninguno | Unicidad por SP | CONFIRMADO | `QueryResumen.txt:L51` |
| `NombreCompleto`| `VARCHAR(100)`| NO | - | Ninguno | Nombre del operador | CONFIRMADO | `QueryResumen.txt:L52` |
| `Correo` | `VARCHAR(100)`| NO | - | Ninguno | Email de contacto | CONFIRMADO | `QueryResumen.txt:L53` |
| `Clave` | `VARCHAR(100)`| NO | - | Ninguno | Contraseña en texto plano | CONFIRMADO | `QueryResumen.txt:L54` |
| `IdRol` | `INT` | NO | FK | Ninguno | `FK -> ROL(IdRol)` | CONFIRMADO | `QueryResumen.txt:L55` |
| `Estado` | `BIT` | NO | - | `1` | `1=Activo, 0=Inactivo` | CONFIRMADO | `QueryResumen.txt:L56` |
| `FechaRegistro` | `DATETIME` | NO | - | `GETDATE()` | Fecha de alta | CONFIRMADO | `QueryResumen.txt:L57` |

---

### 3.2 Tabla: `CLIENTE`
- **Finalidad**: Registrar la información comercial y tributaria de clientes.
- **Evidencia**: `script_clientes.sql:L62`, `Cliente.cs`, `CD_Cliente.cs`.
- **Certeza**: **CONFIRMADO**.

| Campo | Tipo SQL Deducido | Nulo | Clave | Valor Predeterminado | Referencia / Restricción | Certeza | Evidencia |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `IdCliente` | `INT` | NO | PK (IDENTITY) | `IDENTITY(1,1)` | Clave Primaria | CONFIRMADO | `script_clientes.sql:L7` |
| `Apellido` | `VARCHAR(50)` | SI | - | Ninguno | Apellido del cliente | CONFIRMADO | `script_clientes.sql:L7` |
| `Nombre` | `VARCHAR(50)` | SI | - | Ninguno | Nombre del cliente | CONFIRMADO | `script_clientes.sql:L8` |
| `Razon_Social` | `VARCHAR(100)` | SI | - | Ninguno | Nombre Comercial | CONFIRMADO | `script_clientes.sql:L9` |
| `Domicilio` | `VARCHAR(100)` | SI | - | Ninguno | Dirección física | CONFIRMADO | `script_clientes.sql:L10` |
| `Dni` | `VARCHAR(50)` | NO | UNIQUE | Ninguno | DNI / Identificador | CONFIRMADO | `script_clientes.sql:L11` |
| `id_Tipo_dni` | `INT` | SI | FK | Ninguno | `FK -> tipo_dni` | INFERIDO | `script_clientes.sql:L12` |
| `Id_Codigo_Iva` | `INT` | SI | FK | Ninguno | `FK -> codigo_iva` | INFERIDO | `script_clientes.sql:L13` |
| `Cuit` | `VARCHAR(50)` | SI | - | Ninguno | CUIT Tributario | CONFIRMADO | `script_clientes.sql:L14` |
| `Id_Zona` | `INT` | SI | FK | Ninguno | `FK -> zona` | CONFIRMADO | `script_clientes.sql:L15` |
| `Id_Localidad` | `INT` | SI | FK | Ninguno | `FK -> localidad` | CONFIRMADO | `script_clientes.sql:L16` |
| `Id_Provincia` | `INT` | SI | FK | Ninguno | `FK -> provincia` | CONFIRMADO | `script_clientes.sql:L17` |
| `Id_Pais` | `INT` | SI | FK | Ninguno | `FK -> pais` | CONFIRMADO | `script_clientes.sql:L18` |
| `Telefono` | `VARCHAR(50)` | SI | - | Ninguno | Teléfono principal | CONFIRMADO | `script_clientes.sql:L19` |
| `Email` | `VARCHAR(100)` | SI | - | Ninguno | Correo electrónico | CONFIRMADO | `script_clientes.sql:L21` |
| `Id_vendedor` | `INT` | SI | FK | Ninguno | `FK -> vendedor` | CONFIRMADO | `script_clientes.sql:L24` |
| `Latitud` | `DECIMAL(10,8)` | SI | - | Ninguno | Geolocalización Lat | CONFIRMADO | `script_clientes.sql:L25` |
| `Longitug` | `DECIMAL(10,8)` | SI | - | Ninguno | Geolocalización Lng | CONFIRMADO | `script_clientes.sql:L26` |

---

### 3.3 Tabla: `PRODUCTO`
- **Finalidad**: Catálogo de artículos de inventario, costos, precios base y stock.
- **Evidencia**: `actualizacion_productos.sql:L16`, `Producto.cs`, `CD_Producto.cs`.
- **Certeza**: **CONFIRMADO**.

| Campo | Tipo SQL Deducido | Nulo | Clave | Valor Predeterminado | Referencia / Restricción | Certeza | Evidencia |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `IdProducto` | `INT` | NO | PK (IDENTITY) | `IDENTITY(1,1)` | Clave Primaria | CONFIRMADO | `QueryResumen.txt:L72` |
| `Codigo` | `VARCHAR(50)` | NO | UNIQUE | Ninguno | Código Interno | CONFIRMADO | `QueryResumen.txt:L73` |
| `Codigo_de_barra`|`VARCHAR(25)` | NO | - | `''` | Escáner Código Barras | CONFIRMADO | `actualizacion_productos.sql:L19`|
| `Nombre` | `VARCHAR(50)` | NO | - | Ninguno | Nombre comercial | CONFIRMADO | `QueryResumen.txt:L74` |
| `Descripcion` | `VARCHAR(50)` | SI | - | Ninguno | Descripción detallada | CONFIRMADO | `QueryResumen.txt:L75` |
| `IdCategoria` | `INT` | NO | FK | Ninguno | `FK -> CATEGORIA(IdCategoria)`| CONFIRMADO | `QueryResumen.txt:L76` |
| `Stock` | `INT` | NO | - | `0` | Existencia física | CONFIRMADO | `QueryResumen.txt:L77` |
| `Punto_reposicion`|`INT` | NO | - | `0` | Alerta stock mínimo | CONFIRMADO | `actualizacion_productos.sql:L23`|
| `Descuento_Distri`|`DECIMAL(10,2)`| SI | - | `0` | Descuento distribuidora| CONFIRMADO | `actualizacion_productos.sql:L27`|
| `PrecioCompra` | `DECIMAL(10,2)` | NO | - | `0` | Costo base | CONFIRMADO | `QueryResumen.txt:L78` |
| `PrecioVenta` | `DECIMAL(10,2)` | NO | - | `0` | Precio sugerido base | CONFIRMADO | `QueryResumen.txt:L79` |
| `ControlaStock` | `BIT` | NO | - | `1` | `1=Descuenta Stock` | CONFIRMADO | `crear_tablas_ventas_fiscales.sql:L62`|
| `Estado` | `BIT` | NO | - | `1` | `1=Activo, 0=Inactivo` | CONFIRMADO | `QueryResumen.txt:L80` |

---

### 3.4 Tabla: `Lista`
- **Finalidad**: Matriz de precios por lista (Mayorista, Minorista, Promoción) basada en fórmula de costo.
- **Evidencia**: `crear_tabla_lista.sql:L10`, `Lista.cs`, `CD_Lista.cs`.
- **Certeza**: **CONFIRMADO**.

| Campo | Tipo SQL Deducido | Nulo | Clave | Valor Predeterminado | Referencia / Restricción | Certeza | Evidencia |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `Id_Lista` | `INT` | NO | PK (IDENTITY) | `IDENTITY(1,1)` | Clave Primaria | CONFIRMADO | `crear_tabla_lista.sql:L11` |
| `Id_articulo` | `INT` | NO | FK | Ninguno | `FK -> PRODUCTO(IdProducto)` | CONFIRMADO | `crear_tabla_lista.sql:L12` |
| `Descripcion` | `VARCHAR(100)` | SI | - | Ninguno | Nombre de la lista | CONFIRMADO | `crear_tabla_lista.sql:L13` |
| `id_Tipolistas` | `INT` | NO | - | Ninguno | `1=Mayorista, 2=Minorista, 3=Promo`| CONFIRMADO | `crear_tabla_lista.sql:L14` |
| `Recargo` | `DECIMAL(10,2)` | NO | - | `0` | % Utilidad sobre costo | CONFIRMADO | `crear_tabla_lista.sql:L18` |
| `Iva` | `DECIMAL(10,2)` | NO | - | `0` | % Alícuota IVA | CONFIRMADO | `crear_tabla_lista.sql:L17` |
| `Descuento` | `DECIMAL(10,2)` | NO | - | `0` | % Descuento comercial | CONFIRMADO | `crear_tabla_lista.sql:L19` |
| `Importe` | `DECIMAL(10,2)` | NO | - | `0` | **Precio Final Calculado** | CONFIRMADO | `crear_tabla_lista.sql:L15` |

---

### 3.5 Tabla: `VENTA`
- **Finalidad**: Registro de cabecera de comprobantes comerciales y fiscales.
- **Evidencia**: `crear_tablas_ventas_fiscales.sql:L77`, `Venta.cs`, `CD_Venta.cs`.
- **Certeza**: **CONFIRMADO**.

| Campo | Tipo SQL Deducido | Nulo | Clave | Valor Predeterminado | Referencia / Restricción | Certeza | Evidencia |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `IdVenta` | `INT` | NO | PK (IDENTITY) | `IDENTITY(1,1)` | Clave Primaria | CONFIRMADO | `QueryResumen.txt:L114` |
| `IdUsuario` | `INT` | NO | FK | Ninguno | `FK -> USUARIO(IdUsuario)` | CONFIRMADO | `QueryResumen.txt:L115` |
| `IdCliente` | `INT` | SI | FK | Ninguno | `FK -> CLIENTE(IdCliente)` | CONFIRMADO | `crear_tablas_ventas_fiscales.sql:L89`|
| `IdTipoComprobante`|`INT` | SI | FK | Ninguno | `FK -> TipoComprobante` | CONFIRMADO | `crear_tablas_ventas_fiscales.sql:L79`|
| `TipoDocumento` | `VARCHAR(50)` | NO | - | Ninguno | Nombre del comprobante | CONFIRMADO | `QueryResumen.txt:L116` |
| `NumeroDocumento` | `VARCHAR(50)` | NO | - | Ninguno | Nro Correlativo | CONFIRMADO | `QueryResumen.txt:L117` |
| `DocumentoCliente`| `VARCHAR(50)` | SI | - | Ninguno | DNI/CUIT comprador | CONFIRMADO | `QueryResumen.txt:L118` |
| `NombreCliente` | `VARCHAR(100)` | SI | - | Ninguno | Nombre comprador | CONFIRMADO | `QueryResumen.txt:L119` |
| `SubTotal` | `DECIMAL(10,2)` | SI | - | `0` | Neto Gravado Total | CONFIRMADO | `crear_tablas_ventas_fiscales.sql:L116`|
| `TotalIVA` | `DECIMAL(10,2)` | SI | - | `0` | Impuesto IVA Total | CONFIRMADO | `crear_tablas_ventas_fiscales.sql:L117`|
| `TotalDescuento` | `DECIMAL(10,2)` | SI | - | `0` | Total Descuentos | CONFIRMADO | `crear_tablas_ventas_fiscales.sql:L118`|
| `MontoTotal` | `DECIMAL(10,2)` | NO | - | Ninguno | Importe Final Venta | CONFIRMADO | `QueryResumen.txt:L122` |
| `MontoPago` | `DECIMAL(10,2)` | SI | - | Ninguno | Paga con | CONFIRMADO | `QueryResumen.txt:L120` |
| `MontoCambio` | `DECIMAL(10,2)` | SI | - | Ninguno | Vuelto otorgado | CONFIRMADO | `QueryResumen.txt:L121` |
| `IdVentaOriginal` | `INT` | SI | FK | Ninguno | `FK -> VENTA(IdVenta)` (NC) | CONFIRMADO | `crear_tablas_ventas_fiscales.sql:103` |

---

### 3.6 Tabla: `DETALLE_VENTA`
- **Finalidad**: Detalle renglón por renglón de productos vendidos o devueltos.
- **Evidencia**: `crear_tablas_ventas_fiscales.sql:L163`, `Detalle_Venta.cs`.
- **Certeza**: **CONFIRMADO**.

| Campo | Tipo SQL Deducido | Nulo | Clave | Valor Predeterminado | Referencia / Restricción | Certeza | Evidencia |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `IdDetalleVenta` | `INT` | NO | PK (IDENTITY) | `IDENTITY(1,1)` | Clave Primaria | CONFIRMADO | `QueryResumen.txt:L131` |
| `IdVenta` | `INT` | NO | FK | Ninguno | `FK -> VENTA(IdVenta)` | CONFIRMADO | `QueryResumen.txt:L132` |
| `IdProducto` | `INT` | NO | FK | Ninguno | `FK -> PRODUCTO(IdProducto)` | CONFIRMADO | `QueryResumen.txt:L133` |
| `PrecioVenta` | `DECIMAL(10,2)` | NO | - | Ninguno | Precio unitario aplicado | CONFIRMADO | `QueryResumen.txt:L134` |
| `Cantidad` | `INT` | NO | - | Ninguno | Cantidad vendida/devuelta | CONFIRMADO | `QueryResumen.txt:L135` |
| `PorcentajeIVA` | `DECIMAL(5,2)` | SI | - | `0` | % IVA aplicado | CONFIRMADO | `crear_tablas_ventas_fiscales.sql:L167`|
| `ImporteIVA` | `DECIMAL(10,2)` | SI | - | `0` | Importe IVA en pesificación | CONFIRMADO | `crear_tablas_ventas_fiscales.sql:L168`|
| `PorcentajeDescuento`|`DECIMAL(5,2)`| SI | - | `0` | % Descuento renglón | CONFIRMADO | `crear_tablas_ventas_fiscales.sql:L169`|
| `ImporteDescuento`|`DECIMAL(10,2)`| SI | - | `0` | Importe descuento | CONFIRMADO | `crear_tablas_ventas_fiscales.sql:L170`|
| `SubTotal` | `DECIMAL(10,2)` | NO | - | Ninguno | Neto de la línea | CONFIRMADO | `QueryResumen.txt:L136` |
