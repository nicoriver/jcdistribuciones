# INFORME DE CORRECCIÓN DE MIGRACIÓN — TAREA DIST-003B
## Portabilidad e Integridad de la Migración Geográfica de Clientes

**Fecha:** 21 de Octubre de 2026  
**Responsable Técnico:** Agente de Desarrollo / Corrección de Migraciones  
**Coordinación:** ChatGPT  
**Tarea:** DIST-003B — Completar portabilidad de la migración geográfica de clientes  
**Archivo Corregido:** `apps/clientes/migrations/0002_remove_localidad_provincia_alter_cliente_localidad_and_more.py`  
**Archivo de Pruebas Agregado:** `apps/clientes/test_migracion_geografia.py`  
**Rama:** `main`  

---

## 1. Estado Previo del Archivo y Riesgos Concretos

La función `copiar_datos_geografia` en la migración `apps/clientes/migrations/0002_...` presentaba serias deficiencias técnicas que impedían su ejecución segura en entornos heterogéneos (PostgreSQL / SQLite):

1. **Sintaxis SQL incompatible (`INSERT OR IGNORE`):**
   Utilizaba sentencias crudas con `INSERT OR IGNORE INTO geografia_provincia...`. Esta sintaxis es exclusiva de SQLite/MySQL y genera un error fatal de sintaxis en PostgreSQL (`ProgrammingError: syntax error at or near "OR"`).
2. **Silenciamiento indiscriminado de errores (`try ... except Exception: pass`):**
   Todo el bloque de copia estaba envuelto en una captura general. En PostgreSQL (donde `INSERT OR IGNORE` falla), la migración avanzaba silenciosamente sin copiar ningún dato, para luego ejecutar `DeleteModel('Provincia')`, `DeleteModel('Zona')` y `DeleteModel('Localidad')`, eliminando de forma irrecuperable los datos geográficos y corrompiendo las claves foráneas en `Cliente` y `AsignacionZonaVendedor`.
3. **Ausencia de introspección:**
   No verificaba la existencia previa de las tablas origen antes de realizar los `SELECT`.
4. **Desincronización de secuencias en PostgreSQL:**
   La inserción de IDs explícitos no actualizaba las secuencias de PostgreSQL (`pg_get_serial_sequence`), lo que provocaría colisiones de clave primaria en futuros `INSERT` dentro de la aplicación.
5. **Comportamiento indefinido ante colisiones:**
   Ante conflictos de ID o de restricciones de unicidad (`nombre` único en Provincia y Zona; `unique_together` en Localidad), no existía validación explícita.

---

## 2. Decisiones de Diseño Adoptadas

1. **Introspección Agnóstica:**
   Se utiliza `connection.introspection.table_names(cursor)` a través del backend activo de Django. Si ninguna de las tablas origen (`clientes_provincia`, `clientes_zona`, `clientes_localidad`) existe, la función finaliza limpiamente sin intentar operaciones inexistentes.
2. **Modelos Históricos vía ORM:**
   Se accede a los modelos del estado histórico de la migración mediante `apps.get_model()` y se utiliza el alias dinámico provisto por el SchemaEditor (`schema_editor.connection.alias`):
   - Modelos origen: `clientes.Provincia`, `clientes.Zona`, `clientes.Localidad`.
   - Modelos destino: `geografia.Provincia`, `geografia.Zona`, `geografia.Localidad`.
3. **Orden Estricto de Copia para Preservar Relaciones:**
   - **Paso 1: Provincias:** Se copian primero para satisfacer la clave foránea requerida por Localidades.
   - **Paso 2: Zonas:** Se copian transfiriendo `id`, `nombre`, `descripcion`, y asignando por defecto `dia_reparto_defecto=''` y `activa=True`.
   - **Paso 3: Localidades:** Se copian transfiriendo `id`, `provincia_id`, `nombre` y `codigo_postal`.
   - **Paso 4: Conservación de claves foráneas:** Dado que las claves foráneas en `Cliente` (`localidad_id`, `zona_id`) y en `AsignacionZonaVendedor` (`zona_id`) conservan los mismos IDs numéricos, al ejecutarse las operaciones subsiguientes de `AlterField`, Django establece las restricciones hacia `geografia.*` manteniendo intacta la integridad referencial.
4. **Tratamiento Explícito de Conflictos e Idempotencia:**
   - Si un registro ya existe en destino con el mismo ID e idénticos datos, se preserva sin duplicar ni fallar (idempotencia).
   - Si un registro ya existe con el mismo ID pero datos diferentes, o con el mismo valor único pero ID diferente, la migración aborta inmediatamente mediante un `RuntimeError` descriptivo, impidiendo la corrupción de datos o la sobreescritura silenciosa.
5. **Sincronización de Secuencias:**
   Se invoca `connection.ops.sequence_reset_sql(no_style(), [NewProvincia, NewZona, NewLocalidad])`. En PostgreSQL genera y ejecuta las instrucciones `SELECT setval(...)`; en SQLite retorna una lista vacía de forma transparente.

---

## 3. Análisis Explícito de Reversibilidad

> [!WARNING]
> **Evaluación de Rollback:** La migración `clientes.0002` **NO es intrínsecamente reversible de manera segura**.
> - En sentido directo, la migración copia los datos y posteriormente elimina los modelos/tablas `clientes_provincia`, `clientes_zona` y `clientes_localidad` (`DeleteModel`).
> - Al ejecutar un rollback (`migrate clientes 0001`), Django recrea las tablas `clientes_*` totalmente vacías en el esquema antes de ejecutar cualquier función inversa de `RunPython`. Al invertir las operaciones `AlterField` de claves foráneas hacia tablas vacías, se producirían fallos de integridad referencial.
> - Además, la aplicación `geografia` pasa a ser un dominio transversal consumido por múltiples módulos del sistema; revertir y truncar sus tablas podría generar pérdida masiva de datos en otras dependencias.
> - Por tanto, se mantiene `reverse_code=migrations.RunPython.noop` y se desaconseja el rollback en caliente de esta migración.

---

## 4. Archivos Modificados y Agregados

| Archivo | Acción | Descripción |
| :--- | :--- | :--- |
| [`apps/clientes/migrations/0002_remove_localidad_provincia_alter_cliente_localidad_and_more.py`](file:///c:/jcdistribuciones/apps/clientes/migrations/0002_remove_localidad_provincia_alter_cliente_localidad_and_more.py) | Modificado | Reemplazo de SQL nativo SQLite (`INSERT OR IGNORE`) y `except Exception: pass` por ORM histórico, introspección agnóstica, control de conflictos y reseteo de secuencias. |
| [`apps/clientes/test_migracion_geografia.py`](file:///c:/jcdistribuciones/apps/clientes/test_migracion_geografia.py) | Creado | Suite de 6 pruebas de regresión en bases SQLite descartables que validan migración desde cero, migración con datos y claves foráneas, idempotencia, detección de conflictos e irreversibilidad. |
| [`docs/control/DIST-003B_MIGRACION_GEOGRAFIA.md`](file:///c:/jcdistribuciones/docs/control/DIST-003B_MIGRACION_GEOGRAFIA.md) | Creado | Documento de control técnico y funcional de la tarea. |

---

## 5. Pruebas Realizadas y Resultados

Todas las pruebas se ejecutaron sobre bases SQLite temporales y descartables, respetando estrictamente la integridad de `db.sqlite3` y sin conexión al VPS:

1. **Chequeo de Sistema:**
   ```bash
   python manage.py check
   ```
   *Resultado:* `System check identified no issues (0 silenced).` (Código 0).

2. **Detección de Nuevas Migraciones:**
   ```bash
   python manage.py makemigrations --check --dry-run
   ```
   *Resultado:* `No changes detected.` (Código 0).

3. **Verificación de Formato y Espacios:**
   ```bash
   git diff --check
   ```
   *Resultado:* Sin advertencias de espacios ni saltos de línea (Código 0).

4. **Suite Específica de Regresión de la Migración (`apps.clientes.test_migracion_geografia`):**
   - `test_migracion_desde_cero`: Aplica limpiamente sobre base vacía.
   - `test_migracion_con_datos_relacionados`: Comprueba la persistencia íntegra de `Provincia`, `Zona`, `Localidad`, `Cliente` y `AsignacionZonaVendedor` con sus IDs y claves foráneas exactas.
   - `test_idempotencia_segunda_ejecucion`: Constata que la presencia previa de datos idénticos no duplica ni falla.
   - `test_conflicto_id_con_datos_distintos`: Aborta con `RuntimeError` ante discrepancia de ID vs nombre.
   - `test_conflicto_nombre_unico_con_id_distinto`: Aborta con `RuntimeError` ante colisión de campos únicos con IDs incompatibles.
   - `test_evaluacion_reversibilidad_documentada`: Valida la configuración de irreversibilidad informada.
   *Resultado:* **6 tests aprobados (OK) en 6.56s**.

5. **Suite Completa del Proyecto:**
   ```bash
   python manage.py test
   ```
   *Resultado:* **59 tests ejecutados y aprobados al 100% en 156.8s** (Código 0).
