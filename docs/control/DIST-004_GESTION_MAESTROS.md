# INFORME DE CONTROL Y CIERRE — TAREA DIST-004
## Gestión Unificada de Entidades Maestras (Clientes, Productos, Zonas y Vendedores)

**Fecha:** 21 de Octubre de 2026  
**Responsable Técnico:** Agente de Desarrollo  
**Coordinación:** ChatGPT  
**Tarea:** DIST-004 — Completar la gestión de clientes, productos, zonas y vendedores  
**Rama:** `main`  
**Repositorio:** `nicoriver/jcdistribuciones`  

---

## 1. Diagnóstico y Causas Encontradas

Durante la auditoría del panel de gestión y las pantallas preexistentes se detectaron las siguientes inconsistencias técnicas y funcionales:

1. **Formularios desalineados con el modelo de datos vigente:**
   - En `apps/gestion/forms.py`, `ClienteForm` referenciaba `lista_precio_default`. En la migración `apps/clientes/migrations/0003_...`, este campo había sido renombrado a `tipo_lista_precio`.
   - `ClienteForm.save()` intentaba crear usuarios vinculados utilizando el CUIT como contraseña provisional y manejando parámetros obsoletos (`cuit`, `nombre_completo`), lo cual no coincidía con el modelo `Usuario` (`usuarios.models.Usuario`), que utiliza campos separados (`email`, `username`, `nombre`, `apellido`) y requiere contraseñas seguras generadas aleatoriamente.
   - Si la creación del usuario fallaba (p. ej., email duplicado), la creación del cliente se interrumpía por completo.

2. **Inconsistencias en Alícuotas de IVA y Atributos de Producto:**
   - `ProductoForm` intentaba importar e instanciar `AlicuotaIVA` como clave foránea o modelo dinámico, cuando en el modelo `Producto` (`apps/productos/models.py`), `alicuota_iva` está implementado como un `DecimalField` con opciones fijas (`Decimal('0.21')`, `Decimal('0.105')`, etc.).
   - Existían discrepancias en los nombres de atributos: campos nombrados `costo` y `codigo_barra` en formularios/plantillas frente a `costo_base` y `codigo_barras` en el modelo `Producto`.
   - La relación de precios en plantillas se consultaba como `producto.precios_lista.all` en lugar de la relación inversa real del modelo `producto.precios.all`.
   - El formulario de edición de productos permitía o mostraba campos directos de `stock_actual`. Modificar el stock directamente desde una pantalla comercial vulnera el principio de trazabilidad del Kardex (`MovimientoStock`).

3. **Dependencia del Django Admin para Zonas y Vendedores:**
   - En `apps/gestion/templates/gestion/base_gestion.html`, los ítems de navegación lateral para "Vendedores" y "Zonas" apuntaban directamente a `/admin/vendedores/vendedor/` y `/admin/geografia/zona/`.
   - Un usuario con rol de Supervisor o Facturación no necesariamente tiene acceso al Django Admin (`is_staff`), viéndose imposibilitado de dar de alta o editar estas entidades.
   - No existían vistas ni formularios de gestión para `Zona` ni `Vendedor` dentro de `apps/gestion/`.
   - La asignación de zonas a vendedores en el modelo de datos se realiza a través de la tabla intermedia `AsignacionZonaVendedor`. Esta relación debe conservar la trazabilidad histórica: desactivar zonas no debe eliminar registros físicos sino marcarlos con `activo=False`.

4. **Flujo de Autenticación, Redirecciones y Aislamiento de Roles:**
   - Al iniciar sesión, tanto administradores como supervisores caían por defecto en pantallas de vendedores o remitos sin un destino jerárquico claro.
   - El parámetro `?next=` no se conservaba en el formulario de login de forma segura ni se validaba mediante `url_has_allowed_host_and_scheme` para prevenir vulnerabilidades de Open Redirect.
   - Faltaba aislar los accesos por rol para impedir que clientes naveguen rutas de depósito o supervisión, o que roles no autorizados ejecuten operaciones de mutación sin privilegios.

---

## 2. Pantallas y Componentes Implementados

### Pantallas Reutilizadas y Corregidas

1. **Gestión de Clientes (`apps/gestion/templates/gestion/clientes_list.html` y `cliente_form.html`):**
   - Actualización de referencias al nuevo campo `tipo_lista_precio` y campos de nombre del vendedor (`vendedor.nombre_completo`).
   - Paginación estandarizada a 25 registros por página, preservando parámetros de búsqueda (`q`) y filtros en la paginación.
   - Búsqueda compuesta por razón social, nombre de fantasía, CUIT, email y teléfono.
   - Opciones para creación opcional de usuario de portal: casilla de verificación explícita, contraseña provisoria personalizable o generación de contraseña aleatoria segura (nunca se utiliza el CUIT como clave).
   - Manejo de fallos en la creación del usuario sin abortar la creación del cliente, registrando advertencias mediante `django.contrib.messages`.
   - Detección previa de dependencias maestras faltantes (tipos de lista de precio, localidades, vendedores) con alertas directas en la plantilla.

2. **Gestión de Productos (`apps/gestion/templates/gestion/productos_list.html` y `producto_form.html`):**
   - Corrección de mapeo para `codigo_barras`, `costo_base` y `alicuota_iva`.
   - Enlace correcto a precios vigentes mediante `producto.precios.all`.
   - Paginación de 25 registros con persistencia de filtros por categoría y búsqueda textual.
   - Protección de integridad del stock: el campo `stock_actual` se desactiva explícitamente en la edición de producto, incorporando un aviso de que los ajustes de stock deben realizarse mediante movimientos de inventario/Kardex.
   - Detección y advertencia de categorías, marcas o unidades de medida ausentes.

### Pantallas Nuevas Creadas

1. **Listado de Zonas (`apps/gestion/templates/gestion/zonas_list.html`):**
   - Tabla unificada de zonas con nombre, descripción, día de reparto por defecto, total de clientes asociados, estado activo/inactivo y acciones.
   - Búsqueda por texto y filtro por estado (todas / activas / inactivas).
   - Paginación de 25 registros.
   - Botón de conmutación de estado (activar / desactivar) seguro mediante método HTTP POST.

2. **Formulario de Zona (`apps/gestion/templates/gestion/zona_form.html`):**
   - Creación y edición de zonas (`ZonaForm`) con validaciones de unicidad de nombre y normalización de mayúsculas/espacios.

3. **Listado de Vendedores (`apps/gestion/templates/gestion/vendedores_list.html`):**
   - Listado con legajo, nombre completo, teléfono, email, zonas comerciales asignadas activas, total de clientes asignados y estado.
   - Búsqueda por legajo, nombre, apellido, teléfono o email, y filtro por estado.
   - Paginación de 25 registros.
   - Botón de conmutación de estado activo mediante método HTTP POST.

4. **Formulario de Vendedor (`apps/gestion/templates/gestion/vendedor_form.html`):**
   - Formulario de alta y modificación (`VendedorForm`).
   - Selección múltiple de zonas comerciales mediante checkboxes (`ModelMultipleChoiceField`).
   - Sincronización histórica en `AsignacionZonaVendedor`: las zonas desmarcadas pasan a `activo=False` (o se crean nuevas con `activo=True`), preservando el histórico de asignaciones previas sin eliminación física destructiva.

5. **Menú Lateral Unificado (`apps/gestion/templates/gestion/base_gestion.html`):**
   - Enlaces directos a las nuevas pantallas de Zonas y Vendedores (reemplazando los links al Django Admin).
   - Resaltado visual del ítem activo según la URL solicitada.
   - Menú responsive preparado para dispositivos móviles y escritorio.

---

## 3. URLs, Vistas y Matriz de Permisos

Todas las rutas de gestión están protegidas mediante el decorador `@role_required(['SUPERVISOR', 'ADMIN', 'FACTURACION'])`. Los accesos no autorizados retornan `HTTP 403 Forbidden`. Las mutaciones de estado rechazan métodos GET y exigen solicitudes POST con token CSRF válido.

| URL | Vista | Métodos | Permisos Requeridos | Propósito |
|---|---|---|---|---|
| `/gestion/clientes/` | `clientes_list_view` | `GET` | `SUPERVISOR`, `ADMIN`, `FACTURACION` | Listado, búsqueda y paginación de clientes. |
| `/gestion/clientes/nuevo/` | `cliente_crear_view` | `GET`, `POST` | `SUPERVISOR`, `ADMIN`, `FACTURACION` | Alta de clientes y provisión opcional de usuario. |
| `/gestion/clientes/<id>/editar/` | `cliente_editar_view` | `GET`, `POST` | `SUPERVISOR`, `ADMIN`, `FACTURACION` | Edición de datos comerciales y fiscales del cliente. |
| `/gestion/productos/` | `productos_list_view` | `GET` | `SUPERVISOR`, `ADMIN`, `FACTURACION` | Catálogo de productos, filtros por categoría y stock. |
| `/gestion/productos/nuevo/` | `producto_crear_view` | `GET`, `POST` | `SUPERVISOR`, `ADMIN`, `FACTURACION` | Alta de nuevo producto en el catálogo. |
| `/gestion/productos/<id>/editar/` | `producto_editar_view` | `GET`, `POST` | `SUPERVISOR`, `ADMIN`, `FACTURACION` | Modificación comercial de producto (sin alterar stock Kardex). |
| `/gestion/zonas/` | `zonas_list_view` | `GET` | `SUPERVISOR`, `ADMIN`, `FACTURACION` | Listado, búsqueda y filtro de zonas de reparto. |
| `/gestion/zonas/nueva/` | `zona_crear_view` | `GET`, `POST` | `SUPERVISOR`, `ADMIN`, `FACTURACION` | Creación de nueva zona comercial. |
| `/gestion/zonas/<id>/editar/` | `zona_editar_view` | `GET`, `POST` | `SUPERVISOR`, `ADMIN`, `FACTURACION` | Edición de nombre, descripción y día de reparto. |
| `/gestion/zonas/<id>/toggle/` | `zona_toggle_view` | `POST` | `SUPERVISOR`, `ADMIN`, `FACTURACION` | Activación / desactivación de zona (rechaza GET con 405). |
| `/gestion/vendedores/` | `vendedores_list_view` | `GET` | `SUPERVISOR`, `ADMIN`, `FACTURACION` | Listado y búsqueda de equipo de ventas. |
| `/gestion/vendedores/nuevo/` | `vendedor_crear_view` | `GET`, `POST` | `SUPERVISOR`, `ADMIN`, `FACTURACION` | Alta de vendedor con asignación inicial de zonas. |
| `/gestion/vendedores/<id>/editar/` | `vendedor_editar_view` | `GET`, `POST` | `SUPERVISOR`, `ADMIN`, `FACTURACION` | Edición de legajo, datos y sincronización de zonas. |
| `/gestion/vendedores/<id>/toggle/` | `vendedor_toggle_view` | `POST` | `SUPERVISOR`, `ADMIN`, `FACTURACION` | Activación / desactivación de vendedor (rechaza GET con 405). |

### Flujo de Login y Redirecciones
- En `apps/portal/views.py`:
  - `ADMIN` y `SUPERVISOR` son redirigidos a `/gestion/` (`gestion:dashboard`).
  - `DEPOSITO` es redirigido a `/gestion/deposito/pedidos/` (`gestion:deposito_pedidos`).
  - `VENDEDOR` es redirigido a `/portal/vendedor/pedidos/` (`portal:vendedor_pedidos`).
  - `CLIENTE` es redirigido a `/` (`portal:catalogo`), siempre que posea perfil de cliente vinculado.
  - El parámetro `?next=` se preserva de forma segura a través de `url_has_allowed_host_and_scheme(url=next_url, allowed_hosts={request.get_host()})`. Si el destino de `next` pertenece a un rol restringido (p. ej., un cliente intentando ir a `/gestion/`), se ignora y se redirige a su panel correspondiente.

---

## 4. Resultados de Pruebas

### Pruebas Específicas de la Tarea (`apps/gestion/test_gestion_maestros.py`)
Se implementaron 12 tests automatizados que evalúan los requerimientos de la tarea:
1. `test_login_redirect_admin_and_supervisor_to_gestion`: Redirección por defecto al dashboard de gestión.
2. `test_login_redirect_respects_safe_next`: Respeto de parámetro `?next=` seguro.
3. `test_login_redirect_ignores_unsafe_next`: Protección contra redirecciones abiertas maliciosas.
4. `test_unauthorized_role_forbidden_in_gestion`: Verificación de HTTP 403 ante usuarios sin rol de gestión.
5. `test_sidebar_contains_master_links_not_django_admin`: Menú lateral apunta a URLs internas de gestión y no al Django Admin.
6. `test_zona_crud_and_toggle_post_only`: Creación, edición, conmutación POST y rechazo de GET en toggle de zonas.
7. `test_vendedor_crud_and_zone_sync_preserves_history`: Creación, edición y preservación del histórico en `AsignacionZonaVendedor`.
8. `test_cliente_create_with_and_without_user`: Alta de cliente sin usuario y con usuario sin usar el CUIT como clave.
9. `test_cliente_duplicate_cuit_validation`: Validación y rechazo de duplicación de CUIT en clientes.
10. `test_producto_create_with_vat_and_kardex_stock_safety`: Alta de producto con alícuota válida y verificación de que la edición no corrompe el Kardex.
11. `test_paginators_and_search_clientes_productos`: Paginación y preservación de parámetros de búsqueda en listados.
12. `test_missing_master_data_warning_in_template`: Alertas preventivas ante dependencias maestras ausentes.

**Resultado:** **12/12 pruebas PASADAS** exitosamente.

### Suite Completa del Proyecto
- **Total de pruebas:** 71 tests (59 preexistentes + 12 de esta tarea).
- **Estado:** 100% aprobadas sin fallos ni regresiones.

---

## 5. Entidades Maestras que Aún Dependen del Django Admin

Actualmente, las cuatro entidades principales (Clientes, Productos, Zonas y Vendedores) cuentan con interfaz propia en el panel de gestión. Sin embargo, para una autonomía operativa total se identificaron las siguientes entidades auxiliares que aún requieren Django Admin:

1. **Proveedores y Órdenes de Compra (`apps/compras`):**
   - *Prioridad:* **ALTA**.
   - *Motivo:* La reposición de mercadería y la vinculación de costos con proveedores impactan directamente en el cálculo de márgenes y en el Kardex.
2. **Listas de Precios y Reglas de Precios (`apps/productos/models.TipoListaPrecio`, `PrecioProducto`):**
   - *Prioridad:* **ALTA**.
   - *Motivo:* Actualmente `ListaPrecioForm` existe de forma básica, pero no hay un panel masivo para actualizar listas de precios por porcentaje, categoría o marca.
3. **Categorías, Marcas y Unidades de Medida (`apps/productos`):**
   - *Prioridad:* **MEDIA**.
   - *Motivo:* Son requeridas al dar de alta nuevos productos. Si bien no cambian con alta frecuencia, su ausencia bloquea el alta de nuevos ítems en la distribuidora.
4. **Localidades y Provincias (`apps/geografia`):**
   - *Prioridad:* **BAJA**.
   - *Motivo:* Es una estructura estática que rara vez se modifica una vez sembrada la base geográfica de la zona de distribución.

---

## 6. Pasos de Verificación y Despliegue para el VPS

Una vez enviado el commit a `origin/main`, ejecutar en el VPS Linux los siguientes pasos:

1. **Obtener los cambios en el VPS:**
   ```bash
   cd /ruta/al/proyecto
   git pull origin main
   ```

2. **Verificar migraciones y entorno:**
   ```bash
   source .venv/bin/activate
   python manage.py check
   python manage.py makemigrations --check --dry-run
   # (No se requieren migraciones nuevas para esta tarea)
   ```

3. **Recolectar archivos estáticos (si aplica):**
   ```bash
   python manage.py collectstatic --noinput
   ```

4. **Reiniciar el servicio de la aplicación:**
   ```bash
   sudo systemctl restart gunicorn
   ```

5. **Prueba de verificación en el navegador:**
   - Iniciar sesión como usuario Administrador o Supervisor.
   - Constatar que la redirección inicial conduce a `/gestion/`.
   - Navegar en la barra lateral a:
     - `/gestion/clientes/` -> Probar búsqueda y botón "Nuevo Cliente".
     - `/gestion/productos/` -> Probar búsqueda, filtros y botón "Nuevo Producto".
     - `/gestion/zonas/` -> Crear o editar una zona; conmutar estado de actividad.
     - `/gestion/vendedores/` -> Crear o editar un vendedor; verificar selección y guardado de zonas.
   - Comprobar que en dispositivos móviles el menú lateral colapsa y despliega adecuadamente sin desbordes.
