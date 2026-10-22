# INFORME DE CONTROL Y CIERRE — TAREA DIST-005
## Gestión de Proveedores y Unificación Visual del Panel de Gestión

**Fecha:** 22 de Octubre de 2026  
**Responsable Técnico:** Agente de Desarrollo  
**Coordinación:** ChatGPT  
**Tarea:** DIST-005 — Gestión de proveedores y unificación visual del panel  
**Rama:** `main`  
**Repositorio:** `nicoriver/jcdistribuciones`  
**Commit Base:** `d6af4e64fe73fbac1377aa74b3c138facf90d0a3`

---

## 1. Resumen Ejecutivo de la Intervención

La tarea DIST-005 tuvo como propósito completar la administración de entidades comerciales dentro del panel `/gestion/` eliminando el desvío hacia el Django Admin para proveedores, al tiempo que se llevó adelante una reestructuración y unificación visual completa de la interfaz administrativa hacia un esquema sobrio, limpio y profesional.

Principales logros obtenidos:
1. **Módulo Completo de Proveedores en `/gestion/`:** Se implementaron las vistas, formularios y plantillas para listado con búsqueda y paginación (25 registros), alta, edición y activación/desactivación (toggle exclusivo por método POST) de proveedores.
2. **Preservación Estricta de Relaciones de Abastecimiento:** No se implementó borrado físico; se garantiza la integridad referencial con compras registradas (`Compra.proveedor`, `on_delete=PROTECT`) y catálogo (`Producto.proveedor_habitual`, `SET_NULL`). En el listado se agregaron contadores agregados de compras y productos vinculados a cada proveedor.
3. **Unificación Visual Sobria y Estructurada:**
   - **Barra lateral izquierda gris oscuro (`#1e2430`):** Con scroll independiente (`height: calc(100vh - 56px); overflow-y: auto`), enlaces organizados en 4 bloques funcionales (*Inicio*, *Ventas*, *Compras y stock*, *Maestros*), iconos uniformes sin dispersión de colores arcoíris y resaltado de ítem activo en azul primario (`#2563eb`).
   - **Barra superior clara (`bg-white`):** Con marca unificada "JC Distribuciones" (se eliminó el rol "Supervisor" hardcodeado en la marca), acceso directo a Facturación, y menú desplegable del usuario con nombre completo, badge sobrio de rol, acceso al portal comercial y cierre de sesión.
   - **Superficies y Paleta de Color:** Fondo general gris tenue (`#f8fafc`), tarjetas y tablas sobre fondos blancos limpios con bordes suaves, azul como único color primario de acción/selección, y verde, ámbar y rojo estrictamente reservados para estados, advertencias y errores.
4. **Clarificación y Blindaje RBAC (Caso del Usuario Fabio):** Se mantuvo la política de control de acceso basada en roles donde Proveedores, Vendedores y Zonas están restringidos a `ADMIN`, `SUPERVISOR` y superusuarios. Se documenta por qué Fabio (rol `FACTURACION`) no accede a estas entidades sin modificar indebidamente sus privilegios.

---

## 2. Gestión de Proveedores Implementada

### 2.1 Modelo y Formulario (`apps/gestion/forms.py` -> `ProveedorForm`)
Se definió el formulario `ProveedorForm` basado en el modelo `proveedores.Proveedor` con los campos:
- `cuit`: Identificador fiscal tributario. Se aplica limpieza de guiones y puntos en `clean_cuit()`, validación de caracteres exclusivamente numéricos, longitud de 10 u 11 dígitos, y verificación de unicidad excluyendo la propia instancia.
- `razon_social`: Campo obligatorio con placeholder claro.
- `domicilio`: Opcional (`blank=True`).
- `telefono`: Opcional (`blank=True`).
- `email`: Opcional (`blank=True`), validado sintácticamente por `forms.EmailInput`.
- `contacto_nombre`: Opcional (`blank=True`), para individualizar la persona de referencia comercial.
- `activo`: Booleano mediante selector conmutador estilizado.

### 2.2 Vistas y Rutas (`apps/gestion/views.py` y `apps/gestion/urls.py`)
Se crearon y aseguraron cuatro vistas con el decorador `@role_required(['SUPERVISOR', 'ADMIN'])`:

| Ruta URL | Vista | Método | Descripción y Reglas |
|---|---|---|---|
| `/gestion/proveedores/` | `proveedores_list_view` | `GET` | Listado paginado a 25 registros ordenado alfabéticamente por `razon_social`. Búsqueda textual multivariable (`q`) sobre razón social, CUIT, contacto, teléfono y email. Filtro por `estado` (`activo` / `inactivo`). Contadores anotados de `total_compras` y `total_productos`. |
| `/gestion/proveedores/nuevo/` | `proveedor_crear_view` | `GET` / `POST` | Alta de nuevo proveedor con validación transaccional y mensaje flash informativo. |
| `/gestion/proveedores/<id>/editar/` | `proveedor_editar_view` | `GET` / `POST` | Modificación de datos comerciales y fiscales del proveedor existente. |
| `/gestion/proveedores/<id>/toggle/` | `proveedor_toggle_view` | `POST` | Inversión del estado booleano `activo`. **Rechaza peticiones GET retornando HTTP 405 Method Not Allowed**. No realiza borrado físico. |

### 2.3 Plantillas de Proveedores
- `apps/gestion/templates/gestion/proveedores_list.html`: Tabla con diseño limpio, badges de compras y productos asociados, estado con color semántico (verde suave para activo, gris neutro para inactivo), barra de búsqueda, selector de estado y paginación con preservación de parámetros query string.
- `apps/gestion/templates/gestion/proveedor_form.html`: Formulario con indicación explícita de campos requeridos (*), advertencias de errores legibles en español, y botones de confirmación ("Guardar Proveedor" en azul primario) y cancelación ("Cancelar" / "Volver a Proveedores").

---

## 3. Unificación Visual y Arquitectura de Navegación

### 3.1 Estructura del Menú Lateral (Sidebar)
El menú lateral (`apps/gestion/templates/gestion/base_gestion.html`) fue reestructurado en una barra lateral izquierda de tono gris oscuro profesional (`#1e2430`) con scroll independiente (`height: calc(100vh - 56px); overflow-y: auto`), organizada en 4 bloques claramente delimitados:

```text
[ JC Distribuciones ] (TopBar Clara)
├── Inicio
│   └── Dashboard (/gestion/)
├── Ventas
│   ├── Pedidos (/gestion/pedidos/)
│   ├── Bandeja de Facturación (/gestion/facturacion/)
│   ├── Remito Directo (/gestion/remito-directo/)
│   └── Historial de Remitos (/comprobantes/remitos/)
├── Compras y stock
│   ├── Registrar Compra (/admin/compras/compra/add/)
│   ├── Historial de Compras (/admin/compras/compra/)
│   └── Kardex de Stock (/admin/stock/movimientostock/)
└── Maestros
    ├── Clientes (/gestion/clientes/)
    ├── Proveedores (/gestion/proveedores/)  [ADMIN / SUPERVISOR / Superuser]
    ├── Catálogo / Productos (/gestion/productos/)
    ├── Vendedores (/gestion/vendedores/)    [ADMIN / SUPERVISOR / Superuser]
    ├── Zonas de Reparto (/gestion/zonas/)   [ADMIN / SUPERVISOR / Superuser]
    ├── Listas de Precios (/gestion/listas-precio/)
    └── Simulador de Costos (/gestion/simulador-precios/)
```

### 3.2 Homogeneización Gráfica y Paleta de Colores
- **Iconografía Uniforme:** Se eliminaron los colores arcoíris en cada ítem de navegación (`text-warning`, `text-success`, `text-info`), adoptando un tono neutro uniforme (`#94a3b8`) que se ilumina a blanco al pasar el cursor o al estar activo.
- **Color Principal de Acción:** Azul primario (`#2563eb` / `#0d6efd`) como único color de énfasis para ítems seleccionados, botones de acción principal y vínculos destacados.
- **Colores Semánticos Restringidos:** Verde (`#198754`), ámbar (`#ffc107` / `#d97706`) y rojo (`#dc3545`) se reservaron de manera exclusiva para representar estados del negocio (activos, inactivos), alertas operativas y advertencias o errores del sistema.
- **Barra Superior Clara:** Fondo blanco puro (`#ffffff`) con borde inferior sutil (`#e2e8f0`). En el extremo izquierdo se exhibe "JC Distribuciones" como nombre del sistema (sin denominación de rol hardcodeada). En el extremo derecho se despliega el menú de usuario con botón desplegable, indicando nombre, rol en badge sobrio, acceso directo al portal mayorista y salida segura.

---

## 4. Política RBAC y Caso del Usuario Fabio (Rol `FACTURACION`)

Durante la revisión funcional se analizó el escenario del usuario Fabio, quien opera con una sesión que tiene asignado el rol `FACTURACION`.

### Explicación Técnica y Justificación
1. **Regla de Negocio Establecida (DIST-004A y DIST-005):**
   - El rol `FACTURACION` fue concebido para la operativa diaria de emisión de comprobantes, despacho de pedidos y facturación de mostrador.
   - Las entidades maestras estructurantes del modelo comercial (Zonas de Reparto, Vendedores comisionistas y Proveedores de compras) alteran la configuración logística, fiscal y contractual de la empresa.
   - Por esta razón, su administración está estrictamente reservada a usuarios con rol `ADMIN`, `SUPERVISOR` o con privilegio `is_superuser`.
2. **Comportamiento en la Interfaz:**
   - En `base_gestion.html`, los enlaces a *Proveedores*, *Vendedores* y *Zonas de Reparto* están envueltos en:
     ```django
     {% if request.user.rol == 'ADMIN' or request.user.rol == 'SUPERVISOR' or request.user.is_superuser %}
     ...
     {% endif %}
     ```
   - En las vistas backend (`proveedores_list_view`, `vendedores_list_view`, `zonas_list_view`, etc.), el decorador `@role_required(['SUPERVISOR', 'ADMIN'])` responde con **HTTP 403 Forbidden** ante cualquier intento directo de acceso por URL por parte de un usuario con rol `FACTURACION`, `VENDEDOR` o `CLIENTE`.
3. **Preservación de la Base de Datos:**
   - Cumpliendo las directivas de auditoría y control, **no se modificó el rol de Fabio en la base de datos** ni se ampliaron arbitrariamente los permisos del rol `FACTURACION`.
   - Si se requiere que Fabio administre proveedores, vendedores o zonas, la acción requerida es promover su usuario al rol `SUPERVISOR` o `ADMIN` mediante el procedimiento administrativo correspondiente.
4. **Verificación para Roles Autorizados:**
   - Se verificó y testeó que los usuarios con rol `ADMIN`, `SUPERVISOR` y superusuarios visualizan los accesos a Proveedores, Vendedores y Zonas, junto con los botones de acción como "Nuevo vendedor" y "Nuevo proveedor", tanto en resoluciones de escritorio como en dispositivos móviles a través del menú colapsable.

---

## 5. Batería de Pruebas y Validación

### 5.1 Suite Nueva `apps.gestion.test_proveedores` (12 Tests Nuevos)
Se diseñaron 12 pruebas de comportamiento automatizadas que cubren:
- `test_acceso_proveedores_permitido_para_admin_y_supervisor_y_superuser`: Verifica respuesta 200 OK en listado para roles autorizados.
- `test_acceso_proveedores_denegado_para_facturacion_vendedor_cliente`: Verifica respuesta 403 Forbidden para roles no autorizados (listado, alta, edición y toggle).
- `test_creacion_proveedor_exitoso`: Alta válida con normalización de CUIT (limpieza de guiones).
- `test_creacion_proveedor_cuit_duplicado_rechazado`: Impide duplicidad de CUIT.
- `test_creacion_proveedor_cuit_invalido_rechazado`: Valida longitud y caracteres numéricos.
- `test_edicion_proveedor_exitoso`: Modificación de datos y persistencia.
- `test_toggle_proveedor_post_cambia_estado`: Alternancia de estado activo/inactivo por POST.
- `test_toggle_proveedor_get_retorna_405_method_not_allowed`: Rechazo tajante de peticiones GET para cambios de estado.
- `test_proveedor_preserva_relaciones_con_compras_y_productos`: Validación de no borrado físico e integridad con `Compra` y `Producto`.
- `test_sidebar_visibilidad_para_supervisor_y_admin`: Presencia de enlaces en menú lateral para roles facultados.
- `test_sidebar_oculta_proveedores_vendedores_zonas_a_facturacion`: Confirmación de que el menú no expone accesos no permitidos al rol FACTURACION.
- `test_topbar_visual_sin_supervisor_hardcodeado_y_con_dropdown`: Comprobación de marca limpia "JC Distribuciones" y menú desplegable del usuario.

### 5.2 Resultados de Ejecución
- `manage.py check`: 0 fallos identificados.
- `manage.py makemigrations --check --dry-run`: No se requieren migraciones adicionales (el modelo `Proveedor` preexistente se utilizó sin alteraciones de esquema).
- `manage.py test apps.gestion.test_proveedores`: **12 de 12 pruebas aprobadas (OK)**.
- `manage.py test apps.gestion.test_gestion_maestros`: **17 de 17 pruebas aprobadas (OK)**.
- **Suite global previa verificada:** 76 pruebas aprobadas en base local SQLite descartable.

> **Nota sobre el entorno de pruebas:** Todas las pruebas locales fueron ejecutadas sobre la base de datos temporal descartable creada por el runner de pruebas de Django sobre SQLite. La verificación de concurrencia y transaccionalidad definitiva sobre PostgreSQL se llevará a cabo tras la actualización del VPS.

---

## 6. Archivos Afectados

1. **`apps/gestion/forms.py`**:
   - Incorporación de `ProveedorForm` con validación estricta de CUIT y saneamiento de caracteres.
   - Limpieza de definiciones duplicadas en `VendedorForm`.
2. **`apps/gestion/views.py`**:
   - Incorporación de `proveedores_list_view`, `proveedor_crear_view`, `proveedor_editar_view` y `proveedor_toggle_view`.
   - Control RBAC mediante `@role_required(['SUPERVISOR', 'ADMIN'])` y rechazo HTTP 405 para métodos no permitidos en toggle.
3. **`apps/gestion/urls.py`**:
   - Registro de las cuatro rutas de proveedores bajo el namespace `gestion`.
4. **`apps/gestion/templates/gestion/base_gestion.html`**:
   - Rediseño completo de barra superior clara con dropdown de usuario y marca unificada "JC Distribuciones".
   - Reestructuración de sidebar lateral gris oscuro con scroll independiente, 4 bloques organizados, iconos uniformes e indicación de enlaces según RBAC.
5. **`apps/gestion/templates/gestion/proveedores_list.html`**:
   - Nueva plantilla de listado, filtros, indicadores de relaciones y conmutador de estado.
6. **`apps/gestion/templates/gestion/proveedor_form.html`**:
   - Nueva plantilla de formulario de alta y edición de proveedores.
7. **`apps/gestion/test_proveedores.py`**:
   - Suite completa de 12 tests de comportamiento, seguridad, validación y presentación visual.
8. **`docs/control/DIST-005_PROVEEDORES_INTERFAZ.md`**:
   - Documento de control y cierre de la tarea.
