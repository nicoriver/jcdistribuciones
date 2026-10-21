# 07. Brechas Funcionales, Riesgos Técnicos y Deuda Técnica
## Auditoría de Vulnerabilidades, Defectos de Arquitectura y Deuda Acumulada

---

## 1. Introducción
Este documento detalla los hallazgos críticos de **deuda técnica**, **vulnerabilidades de seguridad**, **deficiencias de diseño de datos** y **riesgos operativos** identificados durante la inspección del proyecto .NET de desarrollo y el script SQL Server de producción.

---

## 2. Brechas Funcionales y Deuda Técnica por Dominio

### 2.1 Seguridad y Autenticación
- **Vulnerabilidad Crítica - Almacenamiento de Claves en Texto Plano**:
  - **Evidencia**: En la base de desarrollo (`USUARIO.Clave` - [QueryResumen.txt:L54](file:///c:/jcdistribuciones/jcdistribuciones/QuerySQL/QueryResumen.txt#L54)) y en la base de producción (`regusuarios.contrase` - [script sp produccion.sql:L200](file:///c:/jcdistribuciones/script%20sp%20produccion.sql)), las contraseñas se almacenan sin ningún tipo de hashing o salting.
  - **Riesgo**: Exposición inmediata de credenciales ante accesos no autorizados al script o a la base de datos.
- **Ausencia de Autenticación de Dos Factores (2FA) o Gestión de Sesiones**:
  - El sistema desktop no caduca la sesión por inactividad.

### 2.2 Diseño de Base de Datos y Tipos de Datos
- **Riesgo Impositivo/Monetario - Desbordamiento en `DECIMAL(6,2)`**:
  - **Evidencia**: En el script de producción, campos como `articulo.Costo`, `detallecomprobante.Precio_Unitario` e `Importe` están declarados como `DECIMAL(6,2)`.
  - **Explicación**: Un tipo `DECIMAL(6,2)` asigna 4 dígitos enteros y 2 decimales, lo que limita el valor numérico máximo a **$ 9.999,99**.
  - **Impacto**: Cualquier producto con un costo o precio de venta mayor a $10.000,00 provocará un fallo catastrófico de **Arithmetic Overflow Error** en SQL Server.
- **Inexistencia de Claves Foráneas (`FOREIGN KEY`)**:
  - **Evidencia**: Ninguna de las 56 tablas de producción posee declaraciones `CONSTRAINT FK_... FOREIGN KEY`.
  - **Impacto**: Basura transaccional, registros huérfanos en `detallecomprobante` y registros de clientes/artículos eliminados físicamente manteniendo referencias rotas.
- **Tablas Clonadas / Versionadas sin Normalizar**:
  - Presencia de `articulo1`, `articulo2`, `cliente2`, `comprobante1`, `comprobante2`, `comprobante_anterior`, `detallecomprobante1`, `detallecomprobante2`, `detallecomprobante_ant`, `Lista1`, `Lista2`.
  - **Impacto**: Fragmentación de información histórica. Un reporte anual requiere unir múltiples tablas heterogéneas.

### 2.3 Reglas de Negocio e Impuestos
- **Hardcode de Alícuota de IVA al 21%**:
  - **Evidencia**: En `frmVentasFiscales.cs:L512`, el cálculo del impuesto ejecuta `totalIVA = netoTotal * 0.21m`.
  - **Impacto**: Inexactitud fiscal si el ticket incluye productos gravados al 10.5% (ej: artículos de canasta básica) o 27% (servicios).
- **Riesgo de Duplicación de IVA**:
  - **Evidencia**: En `mdPreciosLista.cs`, se calcula un precio de venta final que ya incluye IVA y se guarda en `Lista.Importe`. Si en la venta fiscal se aplica un 21% adicional sobre dicho precio, el impuesto se duplica.

### 2.4 Control de Stock y Concurrencia
- **Ausencia de Cerrojos Transaccionales Pesimistas o Optimistas**:
  - Ninguno de los procedimientos almacenados de ventas (`usp_RegistrarVenta`, `PA_INS_Facturas`) o código C# utiliza cerrojos atómicos (`SELECT ... FOR UPDATE` o `ROWVERSION` / Timestamp).
  - **Impacto**: Condición de carrera (Race Condition) cuando dos vendedores facturan simultáneamente el último ítem de un producto en stock, produciendo **stock negativo no controlado**.
- **Descuento Duplicado entre Remito y Factura**:
  - En la base de producción, la emisión de un Remito descuenta el stock en `articulo.Cantidad`. Si dicho remito se convierte posteriormente en Factura y el procedimiento de facturación vuelve a restar las unidades, el stock se descuenta dos veces.

---

## 3. Matriz de Evaluación de Riesgos para la Migración

```mermaid
quadrantChart
    title Matriz de Impacto vs Probabilidad de Riesgo
    x-axis Baja Probabilidad --> Alta Probabilidad
    y-axis Bajo Impacto --> Alto Impacto
    quadrant-1 RIESGO CRÍTICO (Acción Inmediata)
    quadrant-2 RIESGO ALTO (Mitigar en Diseño)
    quadrant-3 RIESGO BAJO (Monitorear)
    quadrant-4 RIESGO MEDIO (Planificar)
    Desbordamiento Decimal 6-2: [0.85, 0.95]
    Inexistencia de FKs y Datos Huérfanos: [0.90, 0.85]
    Tablas Clonadas en Producción: [0.80, 0.80]
    Passwords en Texto Plano: [0.95, 0.70]
    Condición de Carrera en Stock: [0.50, 0.75]
    Hardcode IVA 21%: [0.75, 0.60]
```

---

## 4. Estrategia de Mitigación para el Futuro Sistema Django

1. **Remediación de Hashing de Contraseñas**:
   - Implementar el hasher estándar de Django `PBKDF2PasswordHasher` / `BCrypt`.
   - Requerir reseteo obligatorio de contraseña en el primer inicio de sesión post-migración.
2. **Corrección de Tipos Monetarios**:
   - En todos los modelos de Django, utilizar `models.DecimalField(max_digits=14, decimal_places=2)` para soportar montos de hasta $999.999.999.999,99.
3. **Restauración de Integridad Referencial**:
   - Declarar relaciones explícitas `ForeignKey(..., on_delete=models.PROTECT)` en Django para impedir la eliminación accidental de maestros con transacciones.
4. **Control Atómico de Concurrencia**:
   - En la lógica de venta/descuento de stock en Django, envolver las operaciones dentro de un bloque `transaction.atomic()` utilizando `select_for_update()`:
     ```python
     with transaction.atomic():
         producto = Producto.objects.select_for_update().get(id=producto_id)
         if producto.stock < cantidad_solicitada:
             raise ValidationError("Stock insuficiente")
         producto.stock -= cantidad_solicitada
         producto.save()
     ```
