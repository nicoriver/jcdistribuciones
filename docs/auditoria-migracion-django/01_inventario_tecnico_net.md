# 01. Inventario Técnico de la Solución .NET
## Auditoría del Proyecto de Desarrollo - JC Distribuciones

---

## 1. Visión General de la Solución y Proyectos

El proyecto de desarrollo analizado consta de **3 Soluciones Visual Studio (`.sln`)** y **11 Proyectos C# (`.csproj`)** organizados en la raíz y la carpeta `src/`.

```mermaid
graph TD
    subgraph Solución Principal WinForms (.NET Framework 4.7.2)
        SLN1[CursoSistemaVenta.sln] --> CP[CapaPresentacion.csproj]
        SLN1 --> CN[CapaNegocio.csproj]
        SLN1 --> CD[CapaDatos.csproj]
        SLN1 --> CE[CapaEntidad.csproj]
        SLN1 --> SQL[QuerySQL.csproj]
    end

    subgraph Solución Modernización .NET 8 (src/)
        SLN2[src/SistemaVentas.sln] --> CP8[src/CapaPresentacion.Net8.csproj]
        SLN2 --> CNN[src/CapaNegocio.NetStandard.csproj]
        SLN2 --> CDN[src/CapaDatos.NetStandard.csproj]
        SLN2 --> CEN[src/CapaEntidad.NetStandard.csproj]
    end

    subgraph Solución Microservicio AFIP (src/webafip/)
        SLN3[src/webafip/AfipApi.sln] --> API[src/webafip/AfipApi.csproj]
        SLN3 --> MOD[src/webafip/AfipModels.csproj]
        SLN3 --> SRV[src/webafip/AfipServices.csproj]
    end
```

---

## 2. Inventario Detallado de Proyectos

### 2.1 Solución Principal: `CursoSistemaVenta.sln`
- **Ubicación**: `c:\jcdistribuciones\jcdistribuciones\CursoSistemaVenta.sln`
- **Target Framework**: `.NET Framework 4.7.2`
- **Tipo de Aplicación**: Windows Forms Desktop Application (C# Win32)

| Proyecto | Ruta Relativa | Tipo | Responsabilidad / Descripción | Estado |
| :--- | :--- | :--- | :--- | :--- |
| `CapaPresentacion` | `CapaPresentacion/CapaPresentacion.csproj` | WinForms | Interfaz gráfica de usuario, pantallas, modales, generador de comprobantes HTML/PDF. | **CONFIRMADO** (En producción/prueba) |
| `CapaNegocio` | `CapaNegocio/CapaNegocio.csproj` | Class Library | Reglas de negocio, validaciones, calculadora de listas de precios, extensiones de venta. | **CONFIRMADO** |
| `CapaDatos` | `CapaDatos/CapaDatos.csproj` | Class Library | Acceso a SQL Server vía ADO.NET (`SqlConnection`, `SqlCommand`), TVPs (`DataTable`). | **CONFIRMADO** |
| `CapaEntidad` | `CapaEntidad/CapaEntidad.csproj` | Class Library | Modelos de dominio DTO (POCOs) compartidos (`Usuario`, `Producto`, `Venta`, etc.). | **CONFIRMADO** |
| `QuerySQL` | `QuerySQL/QuerySQL.csproj` | Class Library | Scripts DDL/DML del desarrollo (`crear_tabla_lista.sql`, `crear_tablas_ventas_fiscales.sql`). | **CONFIRMADO** |

---

### 2.2 Dependencias y NuGet Packages

| Paquete NuGet | Versión | Proyecto | Finalidad en el Sistema | Evidencia en Código |
| :--- | :--- | :--- | :--- | :--- |
| `FontAwesome.Sharp` | `5.15.3` | `CapaPresentacion` | Iconografía vectorizada para menús y botones del WinForms. | `Inicio.cs:L3` |
| `ClosedXML` | `0.95.4` | `CapaPresentacion` | Exportación e importación de reportes a archivos Excel (`.xlsx`). | `frmReporteVentas.cs:L120` |
| `iTextSharp` / `BouncyCastle` | `5.5.13.2` | `CapaPresentacion` | Conversión de HTML a PDF para comprobantes de venta. | `GeneradorComprobantes.cs:L15` |
| `DocumentFormat.OpenXml`| `2.7.2` | `CapaPresentacion` | Dependencia subyacente de manipulación OpenXML para ClosedXML. | `packages.config` |

---

## 3. Inventario de Formularios UI (`CapaPresentacion`)

| Formulario / Componente | Ruta del Archivo | Responsabilidad / Pantalla | Entidades Relacionadas | Evidencia |
| :--- | :--- | :--- | :--- | :--- |
| `Inicio.cs` | `CapaPresentacion/Inicio.cs` | Contenedor MDI principal. Renderiza menús según permisos del usuario. | `USUARIO`, `PERMISO`, `ROL` | `L45-L100` |
| `Login.cs` | `CapaPresentacion/Login.cs` | Pantalla de inicio de sesión de usuario (Documento + Clave). | `USUARIO`, `ROL` | `L30-L75` |
| `frmUsuarios.cs` | `CapaPresentacion/frmUsuarios.cs` | ABM de usuarios, asignación de roles y estados. | `USUARIO`, `ROL` | `L20-L150` |
| `frmClientes.cs` | `CapaPresentacion/frmClientes.cs` | ABM de clientes (DNI, CUIT, Domicilio, Zona, IVA). | `CLIENTE`, `Zona`, `Localidad` | `L25-L180` |
| `frmProveedores.cs` | `CapaPresentacion/frmProveedores.cs` | ABM de proveedores (Razón Social, CUIT, Contacto). | `PROVEEDOR` | `L20-L140` |
| `frmProducto.cs` | `CapaPresentacion/frmProducto.cs` | ABM de productos, código de barras, stock mínimo. | `PRODUCTO`, `CATEGORIA`, `IVA` | `L30-L210` |
| `frmVentasFiscales.cs` | `CapaPresentacion/frmVentasFiscales.cs` | Punto de Venta Fiscal (Factura A, B, Recibos, Remitos) con cálculo de IVA. | `VENTA`, `DETALLE_VENTA`, `PRODUCTO` | `L1-L550` |
| `frmCompras.cs` | `CapaPresentacion/frmCompras.cs` | Registro de compras a proveedores e impacto en stock. | `COMPRA`, `DETALLE_COMPRA` | `L30-L220` |
| `frmDevolucionesCliente.cs`| `CapaPresentacion/frmDevolucionesCliente.cs`| Búsqueda e ingreso de Notas de Crédito por devoluciones. | `VENTA`, `CN_Venta_Extensiones` | `L25-L190` |
| `frmReporteVentas.cs` | `CapaPresentacion/frmReporteVentas.cs` | Consulta e informes de ventas con exportación a Excel. | `ReporteVenta`, `ClosedXML` | `L20-L160` |
| `frmReporteCompras.cs` | `CapaPresentacion/frmReporteCompras.cs` | Consulta e informes de compras con exportación a Excel. | `ReporteCompra`, `ClosedXML` | `L20-L150` |
| `Modales/mdCliente.cs` | `CapaPresentacion/Modales/mdCliente.cs` | Ventana modal de búsqueda rápida de clientes. | `CLIENTE` | `L15-L80` |
| `Modales/mdProducto.cs` | `CapaPresentacion/Modales/mdProducto.cs` | Ventana modal de catálogo y stock de productos. | `PRODUCTO` | `L15-L90` |
| `Modales/mdPreciosLista.cs`| `CapaPresentacion/Modales/mdPreciosLista.cs`| Calculadora de utilidades, recargos e IVA por lista. | `Lista`, `CN_Lista` | `L20-L125` |
| `GeneradorComprobantes.cs`| `CapaPresentacion/Reportes/GeneradorComprobantes.cs`| Renderizado HTML/Ticket a partir de plantillas. | `Venta`, `Detalle_Venta` | `L1-L250` |

---

## 4. Capa de Negocio (`CapaNegocio`)

| Clase BLL | Ruta | Métodos Principales | Responsabilidad | Evidencia |
| :--- | :--- | :--- | :--- | :--- |
| `CN_Usuario` | `CapaNegocio/CN_Usuario.cs` | `Listar()`, `Registrar()`, `Editar()` | Autenticación y reglas de usuarios. | `L15-L70` |
| `CN_Cliente` | `CapaNegocio/CN_Cliente.cs` | `Listar()`, `Registrar()`, `Editar()` | Validaciones de DNI/CUIT de cliente. | `L15-L80` |
| `CN__Producto` | `CapaNegocio/CN__Producto.cs` | `Listar()`, `Registrar()`, `Editar()` | Registro y modificación de productos. | `L15-L90` |
| `CN_Lista` | `CapaNegocio/CN_Lista.cs` | `CalcularPrecioVenta()`, `ObtenerPrecioProducto()` | **Calculadora de precios**: $\text{Costo} \rightarrow \text{Recargo} \rightarrow \text{IVA} \rightarrow \text{Desc}$. | `L44-L56` |
| `CN_Venta` | `CapaNegocio/CN_Venta.cs` | `ObtenerCorrelativo()`, `Registrar()` | Registro transaccional de venta basica. | `L15-L50` |
| `CN_Venta_Extensiones`| `CapaNegocio/CN_Venta_Extensiones.cs`| `ObtenerVentaPorNumeroDocumento()`, `RegistrarNotaCredito()`, `CalcularTotalesNC()` | **Gestión de devoluciones y Notas de Crédito (NCA/NCB)**. | `L1-L437` |
| `CN_TipoComprobante`| `CapaNegocio/CN_TipoComprobante.cs`| `ListarParaVentas()`, `ObtenerPorId()` | Gestión de comprobantes fiscales (A, B, Recibo, Remito). | `L15-L60` |

---

## 5. Capa de Datos (`CapaDatos`)

| Clase DAL | Ruta | Procedimientos / Consultas Invocadas | Patrón Utilizado |
| :--- | :--- | :--- | :--- |
| `Conexion` | `CapaDatos/Conexion.cs` | Cadena de conexión `ConfigurationManager.ConnectionStrings["cadena_conexion"]` | Centralized Connection Provider |
| `CD_Usuario` | `CapaDatos/CD_Usuario.cs` | `SP_REGISTRARUSUARIO`, `SP_EDITARUSUARIO`, `SP_ELIMINARUSUARIO` | Stored Procedure + Output Parameters |
| `CD_Producto` | `CapaDatos/CD_Producto.cs` | `sp_RegistrarProducto`, `sp_ModificarProducto`, `SP_EliminarProducto` | Stored Procedure + Output Parameters |
| `CD_Venta` | `CapaDatos/CD_Venta.cs` | `usp_RegistrarVenta`, Table-Valued Parameter `EDetalle_Venta` | ADO.NET Single-Roundtrip TVP |
| `CD_Venta_Extensiones`|`CapaDatos/CD_Venta_Extensiones.cs`| `sp_RegistrarVentaFiscal`, `sp_RegistrarNotaCredito` | Transactional TVP Stored Procedure |
| `CD_Lista` | `CapaDatos/CD_Lista.cs` | Consultas SQL directas sobre tabla `Lista` | Inline Dynamic ADO.NET Queries |

---

## 6. Proyectos Adicionales y Microservicios (`src/`)

### 6.1 Intento de Migración a .NET 8 (`src/SistemaVentas.sln`)
- **Archivos**: `src/CapaPresentacion.Net8/CapaPresentacion.Net8.csproj`, `src/CapaNegocio.NetStandard`, etc.
- **Estado**: **PARCIAL / ABANDONADO**. Contiene réplicas parciales de la GUI WinForms migrada a .NET 8 sin completar la totalidad de los eventos.

### 6.2 Microservicio AFIP (`src/webafip/AfipApi.sln`)
- **Archivos**: `src/webafip/AfipApi/Controllers/AfipController.cs`, `src/webafip/AfipServices/AfipService.cs`.
- **Estado**: **PARCIAL / SIMULADO**. Define los DTOs y firmas de servicios para interactuar con los Web Services de la AFIP (WSAA / WSFEv1), pero opera con respuestas mockeadas/simuladas sin certificados digitales reales cargados.
