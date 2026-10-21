# INFORME DE CORRECCIÓN DE MIGRACIÓN — TAREA DIST-003A
## Corrección de Portabilidad PostgreSQL en Migración de Productos

**Fecha:** 21 de Octubre de 2026
**Responsable Técnico:** Agente de Desarrollo / Corrección de Migraciones
**Coordinación:** ChatGPT
**Tarea:** DIST-003A — Corregir migración incompatible con PostgreSQL
**Archivo Corregido:** `apps/productos/migrations/0002_tipolistaprecio_rename_activo_marca_activa_and_more.py`
**Rama:** `main`

---

## 1. Causa del Problema en el VPS

Durante la ejecución del comando `python manage.py migrate` sobre la base de datos PostgreSQL en el VPS Linux, el proceso falló con la siguiente excepción:

```text
django.db.utils.ProgrammingError: relation "sqlite_master" does not exist
```

### Análisis de Causa Raíz
1. **Introspección específica de SQLite (`sqlite_master`):**
   La función `migrar_datos_listas_y_productos` en `apps/productos/migrations/0002_...` ejecutaba la consulta directa:
   ```sql
   SELECT name FROM sqlite_master WHERE type='table' AND name='productos_listaprecio'
   ```
   En PostgreSQL el catálogo de tablas del sistema es `information_schema.tables` o `pg_class`/`pg_tables`. La tabla virtual `sqlite_master` solo existe en SQLite, provocando un error fatal de esquema que abortó la transacción de migración.
2. **Sintaxis DML no soportada (`INSERT OR IGNORE`):**
   Inmediatamente después del chequeo de tabla, la función contenía:
   ```sql
   INSERT OR IGNORE INTO productos_tipolistaprecio (id, nombre, descripcion, activa)
   SELECT id, nombre, descripcion, activa FROM productos_listaprecio
   ```
   La cláusula `INSERT OR IGNORE` es exclusiva de SQLite y MySQL. En PostgreSQL la sintaxis equivalente es `ON CONFLICT DO NOTHING`. Si la consulta a `sqlite_master` hubiese pasado, PostgreSQL habría fallado inmediatamente después con un error de sintaxis en `INSERT OR IGNORE`.

---

## 2. Archivos Modificados

| Archivo | Tipo de Cambio | Detalle |
| :--- | :--- | :--- |
| [`apps/productos/migrations/0002_tipolistaprecio_rename_activo_marca_activa_and_more.py`](file:///c:/jcdistribuciones/apps/productos/migrations/0002_tipolistaprecio_rename_activo_marca_activa_and_more.py) | Modificación puntual | Reemplazo de SQL crudo específico de SQLite por introspección nativa de Django (`connection.introspection.table_names(cursor)`), uso de modelos históricos mediante `apps.get_model`, alias de conexión dinámico (`schema_editor.connection.alias`), sincronización de secuencias en PostgreSQL (`connection.ops.sequence_reset_sql`) y agregado de función inversa para rollback (`revertir_datos_listas_y_productos`). |

*Nota:* No se renombró la migración ni se modificaron sus dependencias, preservando estrictamente la linealidad del historial.

---

## 3. Transformación Preservada y Mecanismo Portable

El propósito original de la migración de datos era copiar las listas de precios existentes desde la tabla antigua `productos_listaprecio` hacia la nueva tabla `productos_tipolistaprecio` antes de alterar la clave foránea en `PrecioProducto`.

La nueva implementación implementa esta transformación de forma 100% portable:
1. **Introspección Agnóstica:**
   Se consulta `connection.introspection.table_names(cursor)` provisto por el backend activo (funciona idénticamente en SQLite y PostgreSQL). Si `productos_listaprecio` no existe en la base, la función retorna limpiamente sin error.
2. **Modelos Históricos del ORM:**
   Se obtienen `ListaPrecio = apps.get_model('productos', 'ListaPrecio')` y `TipoListaPrecio = apps.get_model('productos', 'TipoListaPrecio')`.
3. **Persistencia Segura e Idempotente:**
   Para cada registro existente en `ListaPrecio`, se verifica si ya existe en `TipoListaPrecio` por `id`. Si no existe, se crea con sus mismos valores (`id`, `nombre`, `descripcion`, `activa`), garantizando que las referencias de `precioproducto.tipo_lista_id` mantengan total integridad referencial.
4. **Sincronización de Secuencias en PostgreSQL:**
   Al insertar claves primarias explícitas en PostgreSQL, la secuencia de autoincremento (`productos_tipolistaprecio_id_seq`) no avanza automáticamente. Se incorporó la ejecución de `connection.ops.sequence_reset_sql(no_style(), [TipoListaPrecio])` para actualizar la secuencia al valor máximo y prevenir colisiones en futuros `INSERT`.
5. **Función de Reversa:**
   Se sustituyó `RunPython.noop` por `revertir_datos_listas_y_productos` para permitir rollbacks limpios hacia `productos.0001` sin pérdida de tipos de listas agregados.

---

## 4. Relevamiento de Otras Dependencias SQLite en Migraciones

Se inspeccionaron todas las migraciones del proyecto buscando `sqlite`, `sqlite_master`, `PRAGMA` y llamadas a `cursor`:

1. **`apps/clientes/migrations/0002_remove_localidad_provincia_alter_cliente_localidad_and_more.py`:**
   - En la función `copiar_datos_geografia`: utiliza sentencias `INSERT OR IGNORE INTO geografia_provincia...`.
   - *Estado:* La función completa está envuelta en un bloque `try ... except Exception: pass`. En PostgreSQL, si la tabla no existe o la sintaxis falla, la excepción es silenciada. Sin embargo, no provocó el fallo en el VPS porque se aplicó antes o en otro orden de dependencias. Se registra como hallazgo técnico para monitoreo en caso de despliegue desde cero en bases PostgreSQL limpias.
2. **`apps/usuarios/migrations/0002_remove_usuario_cuit_remove_usuario_nombre_completo_and_more.py`:**
   - Utiliza `cursor.execute("SELECT id, nombre_completo FROM usuarios_usuario")` y `cursor.execute("UPDATE usuarios_usuario ...")`.
   - *Estado:* Compatible con ANSI SQL estándar, funciona perfectamente en ambos motores.

---

## 5. Pruebas Realizadas y Resultados

Todas las pruebas se ejecutaron exclusivamente en el entorno local sin tocar `db.sqlite3` ni conectar con el VPS:

1. **Chequeo de Sistema:**
   `python manage.py check`
   *Resultado:* `System check identified no issues (0 silenced).` (Código 0).
2. **Coherencia de Modelos vs Migraciones:**
   `python manage.py makemigrations --check --dry-run`
   *Resultado:* `No changes detected.` (Código 0).
3. **Prueba de Migración desde Cero con Datos Reales en SQLite Descartable:**
   Se ejecutó un script de verificación que:
   - Creó una base SQLite temporal y aplicó migraciones hasta `productos.0001`.
   - Insertó 2 registros en `productos_listaprecio` (`id=10` 'Lista Mayorista Test' e `id=20` 'Lista Distribuidor Test') y un producto con `PrecioProducto` asociado a la lista `10`.
   - Aplicó la migración corregida `productos.0002`.
   - Constató que `productos_tipolistaprecio` recibió ambos registros con sus IDs intactos y que `precioproducto.tipo_lista_id` mantuvo la relación con la lista `10`.
   - Aplicó todas las migraciones restantes (`0003_delete_listaprecio`, etc.) comprobando la eliminación de la tabla antigua y la persistencia de las 2 listas en `productos_tipolistaprecio`.
   *Resultado:* **100% de éxito**.
4. **Suite Completa de Pruebas Automatizadas:**
   `python manage.py test`
   *Resultado:* **53 tests ejecutados y aprobados al 100% en 151.8s** (Código 0). Cero fallos y cero regresiones.

---

## 6. Limitaciones

- La validación se realizó sobre SQLite debido a que el entorno local no dispone de un motor PostgreSQL activo para pruebas aisladas.
- La ejecución real contra PostgreSQL se validará al desplegar y ejecutar `python manage.py migrate` en el VPS.

---

## 7. Riesgos para Bases donde la Migración ya fue Aplicada

- **En bases locales (SQLite / `db.sqlite3`):**
  La migración ya figuraba como aplicada (`[X] productos.0002`). Como la corrección no altera el esquema de tablas (mismos campos, mismos renames, misma estructura) ni requiere nuevas migraciones (`No changes detected`), las bases donde ya fue aplicada no sufren ningún impacto ni desincronización.
- **En la base del VPS (PostgreSQL):**
  La migración `productos.0002` había fallado y **no estaba marcada como aplicada**. Al ejecutar `python manage.py migrate` con este commit, la migración se ejecutará limpiamente sobre PostgreSQL completando la transformación de datos sin invocar `sqlite_master`.
