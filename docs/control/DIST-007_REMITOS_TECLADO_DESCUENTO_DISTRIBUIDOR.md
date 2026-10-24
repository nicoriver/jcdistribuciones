# INFORME DE CONTROL Y CIERRE — TAREA DIST-007
## Descuento del Distribuidor y Carga de Remitos por Teclado

**Fecha:** 24 de Octubre de 2026  
**Responsable Técnico:** Agente de Desarrollo  
**Tarea:** DIST-007 — Descuento del distribuidor y carga de remitos por teclado  
**Rama:** `main`  
**Repositorio:** `nicoriver/jcdistribuciones`  
**Commit Previo Validado en VPS:** `adf98cb5b8d3cc932b26e3d189a9d12a3c54c623`  
**Suite Previa:** 98 pruebas aprobadas  

---

## 1. Resumen Ejecutivo y Cambios Funcionales

En esta etapa se implementaron dos grandes mejoras funcionales y operativas en el sistema:

### 1.1 Producto: Descuento del Distribuidor (%)
- Se agregó el campo comercial propio `descuento_distribuidor` al modelo `Producto` y al formulario `ProductoForm` (alta y edición comercial).
- **Semántica:** Representa el porcentaje de descuento que el fabricante o proveedor otorga al distribuidor sobre el producto. Es un dato puramente analítico y comercial, separado tanto del recargo/descuento comercial por lista de precios como del descuento aplicado al cliente en el remito.
- **Validación:** Campo de tipo `Decimal` (5 dígitos, 2 decimales), con valor predeterminado `0.00` y validación estricta en modelo y formulario en el rango `[0.00, 100.00]`.
- **Integridad:** Se incorpora a la lista de `campos_comerciales` de edición segura en `ProductoForm.save(update_fields=...)`, protegiendo el campo `stock_actual` de modificaciones concurrentes procedentes del Kardex. En esta fase se almacena sin alterar `costo_base`, listas ni importes históricos de venta.

### 1.2 Cabecera del Remito Directo
- **Cliente:** Mantiene el selector y filtrado por razón social y CUIT.
- **Fecha Comercial:** Se incorporó un selector de fecha comercial (`fecha`), inicializado por defecto en la fecha local de hoy (`timezone.localdate()`). Se persiste en la base de datos y se utiliza en la impresión A4 del comprobante, manteniendo intacto el campo de auditoría `fecha_emision` (DateTimeField automático) para trazabilidad. Para remitos históricos existentes donde `fecha` es nulo, una propiedad inteligente `fecha_comercial` toma como fallback `fecha_emision.date()`, sin reinterpretar registros pasados ni alterar los filtros de informes.
- **Vendedor:** Se eliminó el selector independiente manipulable del remito. Ahora el vendedor se muestra en modo de solo lectura resolviéndose automáticamente desde la ficha del cliente, y el backend valida y exige estrictamente que el vendedor provenga del cliente (`cliente.vendedor`), rechazando cualquier alteración enviada por POST. Si el cliente no posee vendedor asignado, se intercepta la emisión controladamente mostrando una alerta clara con un enlace directo y autorizado para editar la ficha del cliente, evitando errores 500 y prohibiendo vendedores ficticios.
- **Lista de Precios:** Se incorporó un selector de lista de precios activa (`tipo_lista_precio_id`). Al iniciar la vista, el backend detecta dinámicamente la lista con nombre "Minorista" (sin depender de un ID numérico fijo) y la preselecciona por defecto. Si el usuario modifica la lista de precios con renglones ya cargados en pantalla, un diálogo interactivo de confirmación advierte al operador antes de recalcular los precios unitarios, conservando las cantidades y los descuentos porcentuales ingresados. La lista utilizada se persiste en el remito para congelamiento histórico, sin alterar la lista asignada en la ficha del cliente.

### 1.3 Grilla de Carga Rápida y Recorrido Exacto con Enter
Se diseñó la grilla interactiva en `apps/gestion/templates/gestion/remito_directo.html` con las columnas:
`Código | Descripción y Presentación | Cantidad | Precio de lista | Descuento (%) | Total | Quitar`

El recorrido con la tecla <kbd>Enter</kbd> opera según la especificación exacta:
1. **En Código:**
   - Permite ingresar el código interno como texto, preservando ceros iniciales (ej. `00100`).
   - Al pulsar <kbd>Enter</kbd>, busca el producto en el catálogo activo, carga la descripción, selecciona la presentación por defecto o unidad base y obtiene el precio unitario correspondiente a la lista de precios seleccionada.
   - Pasa inmediatamente el foco a **Cantidad** y selecciona su contenido para agilizar la edición.
   - Si el código no existe o el producto está inactivo, muestra un mensaje de error visible, resalta la fila y mantiene el foco en Código seleccionando el texto.
   - Dispone de un botón y modal de búsqueda rápida alternativa por descripción (`#modalBuscarProducto`) que filtra en tiempo real por nombre, código, marca o categoría y traslada el producto seleccionado al renglón.
   - Cuenta con control de identificador de solicitud (`requestId`) por fila para evitar condiciones de carrera donde respuestas asíncronas lentas sobrescriban selecciones posteriores.
2. **En Cantidad:**
   - Al pulsar <kbd>Enter</kbd>, valida que sea un entero positivo mayor a cero (rechaza cantidades fraccionarias sin truncarlas silenciosamente).
   - Recalcula los importes y pasa el foco a **Descuento (%)** seleccionando su contenido.
3. **En Descuento (%):**
   - Inicializado en cero (`0.00`).
   - Acepta porcentajes entre 0 y 100 con formato decimal local (tanto punto como coma).
   - Al pulsar <kbd>Enter</kbd>, valida el rango, recalcula los importes de la fila y los totales del pie, y pasa el foco al campo **Total**.
4. **En Total:**
   - Campo de solo lectura pero enfocable (`tabindex="0"`).
   - Al pulsar <kbd>Enter</kbd>, confirma el renglón y busca la fila siguiente enfocando su campo Código. Si es la última fila, genera automáticamente una nueva fila vacía y enfoca su campo Código.
   - Se bloquea la captura de <kbd>Enter</kbd> como envío del formulario dentro de la tabla (no se emite el comprobante por error desde la grilla).
   - El atajo <kbd>F2</kbd> añade una fila vacía en cualquier momento.
   - La eliminación de filas o corrección manual de valores recalcula de inmediato los totales generales.
   - Una fila nueva vacía al final no bloquea la emisión; una fila incompleta con datos faltantes es señalada como error de validación.
   - En caso de errores en el formulario, se preservan íntegros todos los datos de cabecera y todas las filas ingresadas (`filas_recargadas`).

---

## 2. Campos y Migraciones

Se generaron e integraron dos migraciones aditivas que preservan todos los datos existentes:

### 2.1 Migración `apps/productos/migrations/0005_producto_descuento_distribuidor.py`
```python
migrations.AddField(
    model_name='producto',
    name='descuento_distribuidor',
    field=models.DecimalField(
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='Descuento otorgado por el distribuidor/proveedor. Disponible para cálculos e informes',
        max_digits=5,
        validators=[
            django.core.validators.MinValueValidator(Decimal('0.00')),
            django.core.validators.MaxValueValidator(Decimal('100.00'))
        ],
        verbose_name='Descuento del distribuidor (%)'
    ),
)
```

### 2.2 Migración `apps/comprobantes/migrations/0005_remito_fecha_remito_tipo_lista_precio.py`
```python
migrations.AddField(
    model_name='remito',
    name='fecha',
    field=models.DateField(
        blank=True,
        help_text='Fecha comercial elegida para el comprobante',
        null=True,
        verbose_name='Fecha Comercial'
    ),
),
migrations.AddField(
    model_name='remito',
    name='tipo_lista_precio',
    field=models.ForeignKey(
        blank=True,
        null=True,
        on_delete=django.db.models.deletion.PROTECT,
        related_name='remitos',
        to='productos.tipolistaprecio',
        verbose_name='Lista de Precios Utilizada'
    ),
)
```

---

## 3. Convención del Precio Utilizado y Diagnóstico de la Inconsistencia

### 3.1 Causa de la Inconsistencia Anterior
En la versión previa de `remito_directo.html`, la plantilla HTML contenía:
```html
<option value="{{ p.id }}" data-precio="{{ p.costo_base|floatformat:2 }}">
```
Esto causaba que el atributo `data-precio` inyectara directamente el **costo base** del producto (por ejemplo, `$1,23`) en lugar de su precio de venta en la lista correspondiente, llevando a que productos con valor de venta de miles de pesos aparecieran con valores ínfimos al seleccionarlos. Asimismo, en el backend existía un fallback silencioso que tomaba `producto_obj.costo_base` si no hallaba la lista.

### 3.2 Corrección y Convención Vigente
1. **Obtención del precio:**
   El precio unitario de venta se obtiene de la relación `PrecioProducto` entre el `Producto` y el `TipoListaPrecio` seleccionado:
   $$\text{Precio Base} = \text{precio\_lista.precio\_final}$$
   Si el producto se despacha en una presentación con factor de bulto $F$:
   $$\text{Precio Unitario} = \text{round}(\text{Precio Base} \times F, 2)$$
2. **Prohibición de Fallback Silencioso:**
   Si un producto no tiene precio configurado en la lista seleccionada, el backend rechaza la operación con una `ValidationError` explícita: *"El producto '[Nombre]' [[Código]] no tiene precio definido en la lista '[Lista]'."*
3. **Cálculo por Fila:**
   $$\text{Bruto} = \text{round}(\text{Cantidad} \times \text{Precio Unitario}, 2)$$
   $$\text{Descuento Monetario} = \text{round}\left(\text{Bruto} \times \frac{\text{Porcentaje Descuento}}{100}, 2\right)$$
   $$\text{Total de Fila} = \text{Bruto} - \text{Descuento Monetario}$$
4. **Totales al Pie y en Comprobante:**
   $$\text{Subtotal Bruto} = \sum \text{Bruto}$$
   $$\text{Total Descuento} = \sum \text{Descuento Monetario}$$
   $$\text{Total General} = \sum \text{Total de Fila} = \text{Subtotal Bruto} - \text{Total Descuento}$$
5. **Verificación Caso Testigo:**
   - Fila 1: Precio \$1.000,00, Cantidad 3, Descuento 10% $\rightarrow$ Bruto \$3.000,00, Descuento \$300,00, Total \$2.700,00.
   - Fila 2: Precio \$2.000,00, Cantidad 2, Descuento 0% $\rightarrow$ Bruto \$4.000,00, Descuento \$0,00, Total \$4.000,00.
   - Pie: Subtotal \$7.000,00, Descuento \$300,00, Total General \$6.700,00.
   - Verificado con total coincidencia en base de datos e impresión A4.

---

## 4. Batería de Pruebas y Validación

Se implementó el archivo de pruebas `apps/gestion/test_remitos_teclado_descuento.py` con 10 casos automatizados:

1. `test_descuento_distribuidor_persistencia_y_limites`: Verifica valor por defecto 0.00, persistencia de valores decimales y rechazo de valores `< 0` o `> 100` tanto en modelo como en formulario.
2. `test_edicion_comercial_producto_sin_alterar_stock`: Confirma que la edición comercial guarde el descuento del distribuidor mediante `update_fields` sin sobrescribir variaciones concurrentes de `stock_actual`.
3. `test_fecha_comercial_y_timestamp_creacion`: Valida persistencia de la fecha comercial elegida, conservación separada del timestamp `fecha_emision` y fallback de retrocompatibilidad.
4. `test_vendedor_obtenido_del_cliente_y_rechazo_manipulacion`: Simula intento malicioso en POST enviando un vendedor distinto; comprueba que el backend lo rechaza y utiliza estrictamente el vendedor del cliente.
5. `test_cliente_sin_vendedor_con_mensaje_controlado`: Comprueba que clientes sin vendedor devuelven HTTP 200 con alerta y link de edición, sin error 500 y sin emitir remito.
6. `test_minorista_predeterminada_y_seleccion_otra_lista`: Valida selección por defecto de lista Minorista y posibilidad de emitir remito con lista Mayorista, congelando sus precios específicos.
7. `test_precio_ausente_producto_invalido_y_cantidad_fraccionaria`: Valida bloqueo ante producto sin precio en lista, código inexistente y cantidades decimales/fraccionarias (sin truncar silenciosamente).
8. `test_calculo_caso_testigo_y_coincidencia_con_impresion`: Ejecuta el caso testigo exacto (\$7.000 / \$300 / \$6.700) y valida su renderizado en la plantilla A4 (`comprobantes:imprimir_remito`).
9. `test_preservacion_de_valores_tras_errores`: Valida que ante errores en renglones, el formulario recarga intactos todos los datos ingresados previamente.
10. `test_integridad_numeracion_stock_y_remitos_desde_pedidos`: Valida correlatividad correlativa de `PuntoVentaNumerador`, movimiento de egreso en Kardex (`SALIDA_REMITO`) y respeto absoluto de precios congelados en pedidos facturados a remito.

### Resultados de Ejecución:
- `manage.py check`: 0 problemas detectados.
- `apps.gestion.test_remitos_teclado_descuento`: **10 de 10 pruebas aprobadas (OK)**.
- `apps.comprobantes` y `apps.productos`: **9 de 9 pruebas aprobadas (OK)**.
- Suite global completa: **108 de 108 pruebas aprobadas (OK)** (98 previas + 10 nuevas).

### Declaración de Limitación de Pruebas de Interfaz
Las pruebas automatizadas en Django ejecutan la lógica sobre el motor de plantillas y el ciclo de solicitud/respuesta HTTP en el servidor de pruebas. La navegación física mediante teclado (<kbd>Enter</kbd>, eventos de teclado JS y foco en el navegador real) no cuenta con un motor de automatización de navegador (como Selenium o Playwright) instalado en este entorno de consola; su comportamiento dinámico fue implementado siguiendo rigurosamente las especificaciones de eventos `keydown`, `input` y manipulación del DOM nativo de JavaScript.

---

## 5. Pasos de Actualización en el VPS

Para desplegar estos cambios en el servidor de producción (VPS):

1. **Obtener el código actualizado:**
   ```bash
   cd /ruta/al/proyecto
   git pull origin main
   ```
2. **Aplicar las migraciones aditivas de base de datos:**
   ```bash
   python manage.py migrate
   ```
   *(Aplica `productos 0005` y `comprobantes 0005` sin downtime ni bloqueo de tablas).*
3. **Ejecutar verificación de consistencia del sistema:**
   ```bash
   python manage.py check
   ```
4. **Recargar el servicio web (Gunicorn / uWSGI / systemd):**
   ```bash
   sudo systemctl reload jcdistribuciones  # o restart según configuración local
   ```
