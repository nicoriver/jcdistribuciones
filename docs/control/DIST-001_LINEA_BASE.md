# LÍNEA BASE DEL PROYECTO (DIST-001)
## Sistema Comercial Mayorista — JC Distribuciones

**Fecha:** 21 de Octubre de 2026  
**Responsable Técnico:** Agente de Desarrollo / Auditoría  
**Coordinación:** ChatGPT  
**Tarea:** DIST-001 — Establecer la línea base Git de JC Distribuciones  
**Identidad Git Local:** Saavedra <fabio.rivero@gmail.com>  
**Rama:** `main`

---

## 1. Resumen de Arquitectura y Tecnologías

El proyecto es una aplicación web B2B orientada al comercio mayorista y distribución de alimentos (**JC Distribuciones**). El backend está construido sobre el framework **Django**, organizado en una estructura modular con 12 aplicaciones locales bajo el directorio `apps/` y configuración desacoplada en `config/settings/`.

- **Punto de entrada:** `manage.py` en la raíz del espacio de trabajo.
- **Módulos locales (`apps/`):**
  - `usuarios`: Modelo de usuario personalizado (`Usuario`), autenticación dual (CUIT/DNI o Username) y roles RBAC (`roles.py`).
  - `geografia`: Maestro de Provincias, Localidades y Zonas de reparto logístico.
  - `proveedores`: Maestro de Proveedores y contactos comerciales.
  - `clientes`: Clientes mayoristas, condiciones de IVA, vendedores y asignación de zonas.
  - `productos`: Catálogo, categorías, marcas, alícuotas IVA, productos, presentaciones y listas de precios (`PrecioProducto`).
  - `pedidos`: Flujo de preventa, borradores, revisión, aprobación y congelamiento histórico de precios.
  - `portal`: Interfaz web para clientes (catálogo, carrito, mis pedidos) y preventa móvil para vendedores.
  - `stock`: Configuración general de control de inventario y libro inmutable de movimientos (`MovimientoStock` / Kardex).
  - `compras`: Registro de facturas de compras a proveedores, actualización de costo base y recálculo dinámico de listas de precios.
  - `comprobantes`: Emisión transaccional de Remitos comerciales A4 y Notas de Crédito internas (`NC` y `NCF`).
  - `reportes`: Hojas de ruta por zona y día de reparto, planilla de carga y reporte de ventas por vendedor.
  - `gestion`: Dashboard de supervisión, bandeja de facturación y ABMs administrativos.

---

## 2. Versiones Observadas

Las versiones fueron registradas directamente mediante el intérprete activo en el entorno virtual (`.venv\Scripts\python.exe`):

- **Python:** `3.12.10` (64-bit, Windows)
- **Django:** `6.1.1`
- **Dependencias declaradas (`requirements.txt`) vs Instaladas en `.venv`:**
  - `asgiref`: Declarado `3.12.1` | Instalado `3.12.1` (coincide)
  - `Django`: Declarado `6.1.1` | Instalado `6.1.1` (coincide)
  - `Pillow`: Declarado `11.1.0` | Instalado `12.3.0` (**Diferencia observada**: versión instalada superior a la declarada)
  - `psycopg[binary]`: Declarado `3.3.6` | Instalado `3.3.6` (coincide)
  - `psycopg-binary`: Declarado `3.3.6` | Instalado `3.3.6` (coincide)
  - `python-dotenv`: Declarado `1.2.3` | Instalado `1.2.3` (coincide)
  - `sqlparse`: Declarado `0.6.0` | Instalado `0.6.0` (coincide)
  - `typing_extensions`: Declarado `4.16.0` | Instalado `4.16.0` (coincide)
  - `tzdata`: Declarado `2026.4` | Instalado `2026.4` (coincide)

*Nota:* No se modificó `requirements.txt` para mantener la integridad de las versiones declaradas en esta etapa.

---

## 3. Estado Funcional según la Auditoría Previa

Según el informe detallado en `docs/auditoria/INFORME_ESTADO_ACTUAL.md`, el sistema presenta el siguiente estado:

- **Lógica de negocio implementada y probada:**
  - **Aprobación de pedidos y congelamiento histórico:** Los precios, descuentos e IVA aplicados al momento del envío del pedido se copian inmutablemente a las líneas.
  - **Emisión de Remitos A4:** El remito es el comprobante principal de despacho y cobro, emitido de forma correlativa con bloqueo pesimista (`select_for_update`) sobre `PuntoVentaNumerador`. No discrimina IVA visualmente, cumpliendo la regla comercial solicitada.
  - **Devoluciones y Faltantes:** Diferenciación estricta entre `NCF` (faltante de carga, `reingresa_stock=False`) y `NC` (devolución comercial, `reingresa_stock=True` configurable), con validación de saldos por renglón.
  - **Control de Inventario:** Kardex inmutable con bloqueo en `Producto`.
  - **Logística:** Organización por zonas y días de reparto fijos con generación de hojas de ruta y planillas de carga A4.
- **Módulos no implementados o fuera del MVP inicial:**
  - Cuenta corriente y cobranzas (solo existe saldo inicial en clientes).
  - Facturación electrónica ARCA (AFIP), planificada para una fase posterior.
  - Soporte de pesables y cantidades fraccionadas (kilos/gramos).
  - Lotes y fechas de caducidad para alimentos perecederos.

---

## 4. Estado de Base de Datos: Actual vs Destino

- **Base Actual Local:**  
  SQLite 3 (`db.sqlite3` en la raíz del proyecto). `DATABASES` está hardcodeado a `django.db.backends.sqlite3` en `config/settings/base.py` y `config/settings/production.py`.
- **Base Destino:**  
  PostgreSQL sobre VPS Linux. El driver `psycopg` (v3) ya está instalado en el entorno y referenciado en `.env.example`, pero aún no está cableado en la configuración de Django ni lee variables de entorno mediante `python-dotenv`.
- **Migraciones:**  
  Todas las migraciones están aplicadas y en perfecta sincronía con los modelos (`makemigrations --check --dry-run` reportó `No changes detected`).

---

## 5. Verificaciones Ejecutadas y Limitaciones

1. **Chequeo de Sistema:**  
   `python manage.py check` ejecutado sin advertencias ni errores (0 silenced).
2. **Coherencia de Migraciones:**  
   `python manage.py makemigrations --check --dry-run` ejecutado; modelos y migraciones consistentes.
3. **Suite Automatizada de Tests:**  
   `python manage.py test` ejecutó 40 tests unitarios y de integración sobre una base SQLite en memoria (`:memory:`) aislada y descartable. Resultado: **100% de éxito (40 aprobados)**.
4. **Limitaciones:**  
   - Las pruebas se ejecutaron sobre SQLite; aún no se han probado transacciones ni migraciones directamente sobre un motor PostgreSQL real.
   - No se realizaron pruebas con herramientas de análisis estático (`ruff`, `flake8`, `mypy`) al no encontrarse instaladas en el entorno.

---

## 6. Exclusiones de Git y Seguridad

El archivo `.gitignore` fue configurado exhaustivamente para garantizar que no se incorporen al repositorio:
- Entorno virtual: `.venv/`, `env/`, `venv/`.
- Secretos y variables de entorno: `.env`, `.env.*` (preservando `.env.example` con valores de ejemplo).
- Base de datos local y archivos temporales: `*.sqlite3`, `*.sqlite3-journal`, `*.db`.
- Caché de compilación: `__pycache__/`, `*.pyc`.
- Archivos multimedia y estáticos generados: `media/`, `staticfiles/`.
- Logs y respaldos: `*.log`, `*.bak`, `*.dump`.
- Configuración de editores: `.vscode/`, `.idea/`.

**Inspección de archivos candidatos:**
- `script sp produccion.sql` (627 KB): Fue auditado exhaustivamente. Se constató que contiene únicamente sentencias DDL (`CREATE TABLE`) y procedimientos almacenados (`CREATE PROCEDURE`) de SQL Server. No contiene sentencias `INSERT INTO ... VALUES` con registros de clientes, ventas, correos ni contraseñas reales.
- `.env.example`: Contiene únicamente valores ficticios de plantilla para desarrollo.

---

## 7. Pendientes Técnicos Priorizados

Para las próximas etapas coordinadas por ChatGPT:
1. **[DIST-002] Conexión PostgreSQL en Settings:** Integrar `python-dotenv` y parametrizar `DATABASES` en `base.py` / `production.py` para soportar PostgreSQL en VPS y SQLite en desarrollo local.
2. **[DIST-003] Endurecimiento de Seguridad y Despliegue VPS:** Agregar `gunicorn` a dependencias, configurar directivas HTTPS / CSRF en `production.py`, plantillas de Nginx y servicio `systemd`.
3. **[DIST-004] Numeración Concurrente de Pedidos:** Implementar bloqueo pesimista en la secuencia anual de pedidos (`PED-YYYY-XXXXX`) para prevenir colisiones bajo concurrencia.
4. **[DIST-005] Definición de Cantidades Fraccionadas, Lotes y Vencimientos:** Evaluar si el rubro de alimentos requiere migrar `cantidad` a `DecimalField` e incorporar fechas de caducidad.
5. **[DIST-006] Proceso ETL de Migración:** Construir script de migración histórica desde `script sp produccion.sql` hacia PostgreSQL.

---

## 8. Aclaración sobre Respaldo Remoto

> [!IMPORTANT]
> La creación de este repositorio Git local establece una línea base formal con historial verificable. Sin embargo, **aún no existe vinculación ni respaldo en un repositorio remoto** (GitHub, GitLab u otro). Se recomienda definir el upstream remoto para garantizar la persistencia externa antes de continuar con modificaciones de código.
