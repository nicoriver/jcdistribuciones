# DIST-007A — Informe de Revisión y Corrección Previa al Despliegue

**Fecha:** 24 de Octubre de 2026  
**Rama:** `main`  
**Proyecto Local:** `C:\jcdistribuciones`  
**Commit Base:** `acb3438406fa8d7e79849159d8cd123e3daf2a17` (DIST-007)  
**Estado:** Completado y Validado

---

## 1. Resumen Ejecutivo

En el marco de la revisión técnica previa al despliegue en producción de la tarea **DIST-007**, se identificaron y subsanaron cinco vectores críticos de inconsistencia, seguridad y robustez en la emisión de Remitos Directos de mostrador (`/gestion/remito-directo/`):

1. **Tratamiento consistente de filas vacías e iniciales:** Evitar el bloqueo de la emisión cuando se confirma el último renglón con <kbd>Enter</kbd> (lo cual genera automáticamente una fila nueva con valores por defecto `cantidad=1` y `descuento=0.00`).
2. **Precios exclusivamente resueltos en el servidor:** Eliminación de cualquier fallback o aceptación de precios unitarios enviados por `POST`, exigiendo la selección obligatoria de una lista de precios activa.
3. **Coherencia estricta entre Código, Producto y Presentación:** Invalidación inmediata en frontend de selecciones previas al modificar el código, validación cruzada en backend de correspondencia código-ID, rechazo explícito de presentaciones ajenas y preservación de presentaciones al alternar listas de precios.
4. **Soporte real de coma decimal y sincronización de totales:** Sustitución de inputs numéricos restrictivos por campos decimales textuales, validación completa de filas en el evento `submit`, y alineación del redondeo JavaScript con `Decimal/ROUND_HALF_UP` en casos de medio centavo.
5. **Escape seguro de datos contra XSS:** Reemplazo de serialización manual con filtro `|safe` por la etiqueta nativa `json_script`, erradicación de inyecciones con `innerHTML` sobre datos dinámicos, y sanitización con `format_html`.
6. **Rectificación de documentación de migraciones:** Eliminación de afirmaciones que garantizaban ausencia de bloqueos de tablas o cero downtime sin verificación bajo carga real.

---

## 2. Detalle de Correcciones Implementadas

### Punto 1: Fila Vacía y Emisión Transaccional
- **Diagnóstico:** La función JavaScript `crearFila()` inicializa los renglones con `cantidad=1` y `porcentaje_descuento=0.00`. Al presionar <kbd>Enter</kbd> en el campo Total del último renglón confirmado, se crea automáticamente una nueva fila vacía. Al enviar el formulario, el backend evaluaba `not cant_val`, lo que fallaba debido al valor predeterminado `'1'`, catalogándola erróneamente como un renglón incompleto y bloqueando la emisión con error.
- **Solución implementada:** Se redefinió formalmente en `VentaDirectaRemitoView.post` el criterio de fila vacía:
  ```python
  is_empty_initial = (
      not codigo_val
      and not p_id_val
      and cant_val in ('', '1')
      and (not desc_val or desc_val.replace(',', '.') in ('0', '0.0', '0.00'))
  )
  if is_empty_initial:
      continue
  ```
  Si una fila carece de código y producto pero tiene valores distintos a los iniciales (ej: cantidad modificada o descuento asignado), se preserva y se señala con error explicativo de renglón incompleto.

### Punto 2: Precios Exclusivamente del Servidor
- **Diagnóstico:** Se conservaba una excepción en el backend que leía `precio_unitario[]` de la solicitud POST y un fallback a la lista de precios predeterminada de la ficha del cliente, lo que abría una brecha de manipulación de importes desde el cliente HTTP.
- **Solución implementada:**
  - Se eliminó completamente la lectura de precios unitarios enviados por POST en `VentaDirectaRemitoView`.
  - El precio unitario se calcula **estrictamente en el servidor** multiplicando el `precio_final` de la lista por el `factor_conversion` de la presentación, aplicando redondeo `ROUND_HALF_UP`.
  - Si falta la lista de precios en la cabecera o el ID no es válido, se bloquea la emisión con mensaje explícito: `"Debe seleccionar una lista de precios activa válida."`.
  - Se actualizó la prueba histórica `test_venta_directa_remito_mostrador_supervisor` en `apps/gestion/tests.py` para suministrar la lista de precios en la petición.
  - El circuito de pedidos previos (`apps.pedidos`) permanece inalterado, manteniendo sus precios históricos congelados al emitir comprobantes.

### Punto 3: Coherencia entre Código, Producto y Presentación
- **Diagnóstico:** Si el operador modificaba el texto del código tras haber seleccionado un producto, el campo oculto `producto_id[]` conservaba la referencia previa. Además, si se enviaba una presentación perteneciente a otro producto o inexistente, el sistema la degradaba silenciosamente a factor 1.
- **Solución implementada:**
  - **Frontend:** Al dispararse el evento `input` sobre `.input-codigo`, se limpian de inmediato los identificadores (`row.dataset.productoId = ''`, `input-producto-id.value = ''`), descripciones, insignias de stock y totales en dataset.
  - **Backend:** Se implementó verificación cruzada:
    ```python
    if codigo_val and p_id_val:
        if not prod_by_code or not prod_by_id or prod_by_code.id != prod_by_id.id:
            errores_filas.append(f"Renglón #{idx+1}: Incoherencia entre el código '{codigo_val}' y el producto seleccionado.")
            continue
    ```
  - **Validación de Presentación:** Si se envía `presentacion_id`, se exige que pertenezca inequívocamente al producto (`Presentacion.objects.filter(id=..., producto=producto)`). De no existir o pertenecer a otro producto, se rechaza con error explícito sin degradación silenciosa.
  - **Cambio de Lista:** En `recalcularTodasLasFilas()`, se lee la presentación ya seleccionada en el renglón (`selectPres.selectedIndex`) para actualizar únicamente el precio base y totales, sin resetear la selección a la unidad base predeterminada.

### Punto 4: Totales, Validación del Navegador y Redondeo
- **Soporte de Coma Decimal:** En navegadores estándar basados en Chromium/Firefox, los elementos `<input type="number">` descartan la entrada al ingresar comas en ciertas configuraciones regionales (`.value` devuelve cadena vacía). Se transformó a `<input type="text" inputmode="decimal">`, permitiendo ingresar indistintamente `,` o `.` tanto en frontend como en backend.
- **Limpieza de Totales Huérfanos:** Cuando un producto no tiene precio definido en la lista activa, se resetean a `'0'` los atributos `data-bruto`, `data-descuento-monetario` y `data-total-fila`, asegurando que el pie permanente recalcula inmediatamente a cero.
- **Validación Previa al Submit:** Se intercepta el evento `submit` del formulario para validar exhaustivamente que no existan renglones con precios en cero, cantidades inválidas o descuentos fuera de rango [0, 100], garantizando al menos un producto válido antes de deshabilitar el botón y mostrar el indicador de carga.
- **Redondeo Canónico:** Se implementó en JavaScript la fórmula matemática exacta:
  ```javascript
  function roundHalfUp(num, decimals = 2) {
      if (isNaN(num) || num === null || num === undefined) return 0;
      return Number(Math.round(Number(num + 'e' + decimals)) + 'e-' + decimals);
  }
  ```
  Evita inconsistencias de punto flotante binario (ej. `1.005` redondeando hacia abajo) y coincide exactamente con `Decimal.quantize(..., rounding=ROUND_HALF_UP)`.

### Punto 5: Escape Seguro de Datos
- **Catálogo Seguro:** Se reemplazó el bloque `<script>{{ catalog_data_json|safe }}</script>` por la etiqueta segura de Django:
  ```django
  {{ catalog_data|json_script:"catalogDataScript" }}
  ```
  En la vista, `_get_remito_directo_context()` pasa la estructura nativa de Python `catalog_data` como diccionario, delegando la serialización segura y el escape de caracteres `<script>` a Django.
- **Erradicación de `innerHTML` con Datos de Usuario:** La construcción de filas en el modal de búsqueda de productos y la actualización del vendedor (`actualizarVendedor`) ahora emplean creación de nodos DOM (`document.createElement`, `textContent` y `replaceChildren`), previniendo inyecciones XSS.
- **Alerta de Vendedor Faltante:** Se sustituyó `mark_safe` con interpolación de cadenas por `format_html`:
  ```python
  messages.error(
      request,
      format_html(
          "El cliente <strong>{}</strong> no tiene un vendedor asignado. "
          "Debe asignarle un vendedor para poder emitir el remito. "
          "<a href='{}' class='alert-link fw-bold' target='_blank'>Haga clic aquí para editar la ficha del cliente</a>.",
          cliente.razon_social,
          edit_url
      )
  )
  ```

---

## 3. Pruebas Automatizadas Incorporadas

En `apps/gestion/test_remitos_teclado_descuento.py` se añadieron 5 nuevas pruebas unitarias e integrales que cubren todos los escenarios exigidos:

1. `test_dist007a_fila_final_vacia_con_valores_iniciales_se_ignora`: Verifica que un POST con un producto válido seguido de una fila final vacía con valores iniciales (`cant=1`, `desc=0.00`) se emite exitosamente con exactamente un solo detalle de remito.
2. `test_dist007a_precios_exclusivamente_del_servidor_y_rechazo_lista_ausente_invalida`:
   - Envío de precio manipulado en POST (`$1.00` en vez de `$1000.00`): el comprobante ignora el valor manipulado y calcula con el precio oficial de la lista.
   - Envío con lista ausente: rechaza la emisión sin sustituir por la lista del cliente.
   - Envío con ID de lista inválido/inexistente: bloquea la emisión con mensaje de error controlado.
3. `test_dist007a_coherencia_codigo_producto_y_rechazo_presentacion_invalida`:
   - Código de producto A con ID de producto B: rechaza la emisión por incoherencia.
   - Presentación de otro producto enviada en el renglón: rechaza con error explícito de pertenencia, sin convertir a unidad base.
4. `test_dist007a_presentacion_alternativa_factor_mayor_a_uno`: Prueba la emisión con una presentación alternativa de factor 6 (Pack x6), verificando multiplicación de precio unitario, subtotal y descuento físico de stock en inventario (factor aplicado una sola vez).
5. `test_dist007a_escape_seguro_caracteres_especiales_html`:
   - Producto con `<script>alert("xss")</script>` y comillas en su nombre se serializa vía `json_script` con escape seguro unicode `\u003Cscript\u003E`.
   - Cliente sin vendedor con etiquetas HTML `<img src=x onerror=alert(1)>` en su razón social se escapa correctamente mediante `format_html` como entidades `&lt;img ...&gt;`.

---

## 4. Resultados de Verificación

- **Chequeo de Sistema:**
  ```bash
  python manage.py check
  # System check identified no issues (0 silenced).
  ```
- **Chequeo de Migraciones Pendientes:**
  ```bash
  python manage.py makemigrations --check --dry-run
  # No changes detected
  ```
- **Suite de Pruebas de Remitos Directos:**
  ```bash
  python manage.py test apps.gestion.test_remitos_teclado_descuento --keepdb
  # Ran 15 tests in 55.637s - OK
  ```
- **Suite Completa del Proyecto:**
  ```bash
  python manage.py test --keepdb
  # Ran 113 tests in 676.474s - OK (100% aprobadas, 0 errores, 0 fallos)
  ```

---

## 5. Declaración de Limitaciones Técnicas

1. **Pruebas Físicas de Navegador:**
   En el entorno local de consola no se encuentra disponible un entorno de automatización de navegador headless (como Selenium, Playwright o Puppeteer) ni un navegador gráfico interactivo. Por consiguiente, la validación física en tiempo real de la secuencia de foco (<kbd>Código</kbd> → <kbd>Enter</kbd> → <kbd>Cantidad</kbd> → <kbd>Enter</kbd> → <kbd>Descuento</kbd> → <kbd>Enter</kbd> → <kbd>Total</kbd> → <kbd>Enter</kbd> → nueva fila) y del formateo interactivo de la coma decimal **queda expresamente declarada como pendiente de comprobación manual por parte del operador**.
2. **Concurrencia y Bloqueos en Migraciones:**
   Se rectificó la documentación anterior (`DIST-007`). No se garantiza a priori que las migraciones `0005` de `productos` y `comprobantes` se apliquen sin bloqueos transitorios de tabla (`ACCESS EXCLUSIVE` durante operaciones `ALTER TABLE` en PostgreSQL) ni con cero downtime en entornos de alta concurrencia; cualquier garantía de este tipo requiere pruebas de carga de base de datos directas en el motor de producción.
