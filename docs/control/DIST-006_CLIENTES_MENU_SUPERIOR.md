# INFORME DE CONTROL Y CIERRE — TAREA DIST-006
## Corrección de Listado de Clientes sin Vendedor y Menú Superior de Navegación

**Fecha:** 22 de Octubre de 2026  
**Responsable Técnico:** Agente de Desarrollo  
**Coordinación:** ChatGPT  
**Tarea:** DIST-006 — Corregir listado de clientes sin vendedor y agregar navegación superior  
**Rama:** `main`  
**Repositorio:** `nicoriver/jcdistribuciones`  
**Commit de Referencia:** `2516388b577e6adb343352355434a6e2d30f346e`

---

## 1. Diagnóstico y Causa Confirmada del Error 500

### 1.1 Reproducción del Problema
Se reprodujo el error registrando un cliente mediante POST en `/gestion/clientes/nuevo/` sin seleccionar un vendedor (`vendedor=''`).
- **Comportamiento observado:**
  1. La operación de guardado en la base de datos se ejecutó exitosamente: el registro de `Cliente` fue creado con `vendedor_id = NULL`.
  2. La vista retornó una respuesta HTTP 302 con encabezado `Location: /gestion/clientes/`.
  3. El navegador siguió la redirección a `/gestion/clientes/`.
  4. Al intentar renderizar la plantilla `apps/gestion/templates/gestion/clientes_list.html`, el servidor falló inmediatamente con **HTTP 500 (Server Error)**.
  5. A partir de ese momento, cualquier solicitud GET a `/gestion/clientes/` devolvía un error 500 persistente mientras el cliente sin vendedor estuviera presente en la base de datos.

### 1.2 Causa Técnica
En la plantilla `clientes_list.html` existía la siguiente instrucción de renderizado:
```django
{{ c.vendedor.nombre_completo|default:c.vendedor.nombre|default:"Casa Central" }}
```
**Mecanismo de falla en el motor de plantillas de Django:**
1. Los filtros de plantilla de Django evalúan sus argumentos antes de ejecutarse.
2. En la expresión `|default:c.vendedor.nombre`, el argumento `c.vendedor.nombre` es interpretado como una variable de contexto a resolver.
3. Dado que `c.vendedor` es `None`, el motor intenta resolver el atributo `nombre` sobre `None` mediante `getattr(None, 'nombre')`, lo que lanza `AttributeError: 'NoneType' object has no attribute 'nombre'`.
4. En Django, la resolución de variables simples en el cuerpo de la plantilla sustituye silenciosamente los valores faltantes por cadenas vacías (`""`). Sin embargo, en la resolución de **argumentos de filtros**, `_resolve_lookup` eleva la excepción `django.template.base.VariableDoesNotExist: Failed lookup for key [nombre] in None`.
5. Esta excepción no es capturada por la vista, provocando la interrupción del ciclo de renderizado y el error 500 fatal.
6. Se detectó una vulnerabilidad análoga en la columna adyacente:
   ```django
   {{ c.tipo_lista_precio.nombre|default:c.lista_precio_default.nombre|default:"Estándar" }}
   ```
   donde un cliente sin lista de precios asignada provocaba el mismo fallo al resolver `c.lista_precio_default.nombre`.

---

## 2. Solución Implementada para la Cartera de Clientes

### 2.1 Sustitución de Filtros por Condiciones Explícitas
Se reemplazaron todas las expresiones vulnerables en `apps/gestion/templates/gestion/clientes_list.html` por estructuras condicionales `{% if %}` explícitas que nunca evalúan atributos sobre objetos nulos:

- **Vendedor asignado:**
  ```django
  {% if c.vendedor %}
      <span class="text-dark fw-semibold">{{ c.vendedor.nombre_completo }}</span>
  {% else %}
      <span class="text-muted fst-italic">Sin vendedor asignado</span>
  {% endif %}
  ```
- **Zona y Día de Reparto:**
  ```django
  {% if c.zona %}
      <div class="fw-semibold text-dark">{{ c.zona.nombre }}</div>
  {% else %}
      <div class="text-muted small">Sin zona asignada</div>
  {% endif %}
  {% if c.dia_reparto %}
      <small class="text-muted">{{ c.get_dia_reparto_display }}</small>
  {% else %}
      <small class="text-muted">Sin día fijo</small>
  {% endif %}
  ```
- **Condición de IVA:**
  ```django
  {% if c.condicion_iva %}
      <span class="badge bg-secondary-subtle text-dark border">{{ c.condicion_iva.codigo }}</span>
  {% else %}
      <span class="badge bg-light text-muted border">Sin IVA</span>
  {% endif %}
  ```
- **Tipo de Lista de Precios:**
  ```django
  {% if c.tipo_lista_precio %}
      <span class="badge bg-primary-subtle text-primary border border-primary-subtle">{{ c.tipo_lista_precio.nombre }}</span>
  {% else %}
      <span class="badge bg-light text-muted border">Sin lista asignada</span>
  {% endif %}
  ```
- **Domicilio y Localidad:** Concatenación limpia evitando errores si `localidad` o `provincia` son `None`.

### 2.2 Filtros de Búsqueda de Clientes sin Vendedor o sin Zona
En `apps/gestion/views.py` (`clientes_list_view`), se añadió compatibilidad para filtrar explícitamente clientes no asignados:
```python
if vendedor_id == 'sin_vendedor':
    clientes_qs = clientes_qs.filter(vendedor__isnull=True)
elif vendedor_id and vendedor_id.isdigit():
    clientes_qs = clientes_qs.filter(vendedor_id=int(vendedor_id))

if zona_id == 'sin_zona':
    clientes_qs = clientes_qs.filter(zona__isnull=True)
elif zona_id and zona_id.isdigit():
    clientes_qs = clientes_qs.filter(zona_id=int(zona_id))
```
Esto permite a los supervisores consultar de inmediato los clientes pendientes de asignación comercial o logística.

### 2.3 Claridad en el Formulario de Alta y Edición
En `apps/gestion/templates/gestion/cliente_form.html`:
- Se eliminaron asteriscos erróneos en campos que son opcionales en el modelo (`condicion_iva` y `tipo_lista_precio`).
- Se verificó que los datos ingresados por el usuario se conserven íntegros en el formulario ante errores de validación (por ejemplo, CUIT mal formado) y que los mensajes de error se muestren de forma visible en español.

---

## 3. Implementación del Menú Superior de Navegación

Se incorporó la barra de navegación superior horizontal en `apps/gestion/templates/gestion/base_gestion.html` conservando el estilo sobrio aprobado:

### 3.1 Estructura y Vínculos Reutilizados
El menú superior presenta cuatro módulos principales:
1. **Ventas (Menú desplegable):**
   - *Pedidos* (`gestion:pedidos_list`)
   - *Bandeja de Facturación* (`gestion:bandeja_facturacion`)
   - *Remito Directo* (`gestion:remito_directo`)
   - *Historial de Remitos* (`comprobantes:remitos_list`)
2. **Productos:**
   - Acceso directo a *Catálogo / Productos* (`gestion:productos_list`).
3. **Clientes:**
   - Acceso directo a *Cartera y Padrón de Clientes* (`gestion:clientes_list`).
4. **Informes (Menú desplegable):**
   - *Hoja de Ruta (Reparto)* (`reportes:hoja_ruta`)
   - *Ventas por Vendedor* (`reportes:ventas_vendedores`)
   - *Kardex de Stock* (`/admin/stock/movimientostock/`) [solo usuarios con permisos de staff/admin]
   - *Historial de Compras* (`/admin/compras/compra/`) [solo usuarios con permisos de staff/admin]

### 3.2 Indicación de Módulo Activo
El enlace correspondiente al módulo activo adquiere automáticamente la clase CSS `.active` con color azul primario (`#2563eb`) y fondo suave (`#eff6ff`) basándose en `request.resolver_match.url_name` y `request.resolver_match.app_name`.

### 3.3 Adaptabilidad a Dispositivos Móviles
- En pantallas grandes (`lg` y superiores), los módulos se despliegan horizontalmente en la barra superior junto al botón de Facturación y el menú de usuario.
- En pantallas medianas y móviles (`<lg`), la barra superior se adapta mediante colapso responsive (`#topbarNavCollapse`) controlado por un botón hamburguesa, evitando desbordar la pantalla o encimarse con el menú del usuario.
- Se añadió un botón específico en dispositivos móviles para alternar el menú lateral izquierdo (`#sidebarMenu`).
- Se respetó la paleta cromática estricta: fondo blanco (`#ffffff`), grises (`#475569`, `#1e293b`), bordes sutiles (`#e2e8f0`) y azul primario (`#2563eb`).

---

## 4. Batería de Pruebas y Validación

### 4.1 Suite `apps.gestion.test_clientes_navegacion` (10 Pruebas Nuevas)
Se implementaron 10 pruebas automatizadas que verifican:
1. `test_listado_clientes_con_cliente_sin_vendedor_retorna_200_ok`: Confirma respuesta HTTP 200 y presencia del texto *"Sin vendedor asignado"*.
2. `test_listado_clientes_con_cliente_con_vendedor_muestra_nombre_completo`: Confirma visualización del nombre y apellido del vendedor.
3. `test_listado_clientes_sin_ninguna_relacion_opcional_retorna_200_ok`: Valida clientes sin vendedor, zona, localidad, IVA ni lista de precios.
4. `test_alta_cliente_sin_vendedor_con_follow_redirige_y_muestra_listado`: Alta completa con `follow=True` verificando el guardado en base de datos y la renderización final de la lista.
5. `test_edicion_cliente_vaciando_vendedor_persiste_y_renderiza`: Edición de cliente eliminando el vendedor asignado.
6. `test_listado_datos_mixtos_busqueda_y_paginacion`: Prueba con 30 clientes combinados, paginación a 25 registros y búsqueda textual activa.
7. `test_formulario_conserva_datos_y_muestra_errores_ante_validacion_invalida`: Retención de datos y mensajes de error ante CUIT inválido.
8. `test_menu_superior_contiene_accesos_principales`: Presencia de *Ventas*, *Productos*, *Clientes* e *Informes* con sus respectivas rutas.
9. `test_modulo_activo_marcado_adecuadamente_segun_vista`: Verificación de la clase `.active` en el módulo navegado.
10. `test_menu_superior_conserva_datos_usuario_y_rol`: Integridad de los datos de sesión en la barra superior.

### 4.2 Resultados de Ejecución
- `manage.py check`: 0 problemas detectados.
- `manage.py makemigrations --check --dry-run`: No se detectaron cambios pendientes en las migraciones.
- `apps.gestion.test_clientes_navegacion`: **10 de 10 pruebas pasadas (OK)**.
- `apps.gestion.test_proveedores`: **12 de 12 pruebas pasadas (OK)**.
- Suite completa ejecutada sobre base de datos SQLite temporal descartable.

---

## 5. Archivos Afectados

1. **`apps/gestion/templates/gestion/clientes_list.html`**:
   - Reemplazo de filtros vulnerables por bloques condicionales explícitos.
   - Incorporación del texto *"Sin vendedor asignado"* y visualización segura de todas las relaciones opcionales.
   - Soporte para selector de filtro *"Sin vendedor asignado"* y *"Sin zona asignada"*.
2. **`apps/gestion/views.py`**:
   - Adaptación de `clientes_list_view` para filtrar `vendedor__isnull=True` y `zona__isnull=True`.
3. **`apps/gestion/templates/gestion/cliente_form.html`**:
   - Ajuste de etiquetas de campos opcionales.
4. **`apps/gestion/templates/gestion/base_gestion.html`**:
   - Incorporación del menú superior responsive (*Ventas*, *Productos*, *Clientes*, *Informes*).
   - Estilos CSS para ítems activos y dropdowns.
   - Adaptabilidad móvil con togglers diferenciados para menú superior y menú lateral.
5. **`apps/gestion/test_clientes_navegacion.py`**:
   - Archivo de pruebas automatizadas que cubren todos los escenarios de clientes y navegación.
6. **`docs/control/DIST-006_CLIENTES_MENU_SUPERIOR.md`**:
   - Documento técnico de control y cierre.
