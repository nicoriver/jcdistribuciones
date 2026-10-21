# Guía de Configuración de Entornos y Bases de Datos
## Sistema Comercial Mayorista — JC Distribuciones

**Documento de Control:** `docs/configuracion/ENTORNOS.md`
**Referencia Técnica:** Tarea DIST-002
**Framework:** Django 6.1.1 / Python 3.12.10

---

## 1. Introducción y Arquitectura de Settings

El proyecto implementa una arquitectura de configuración desacoplada bajo `config/settings/`:
- `config/settings/base.py`: Configuración común, carga de `.env`, funciones de parseo seguro y constructor de base de datos.
- `config/settings/local.py`: Entorno de desarrollo local (activo por defecto en `manage.py`, `wsgi.py` y `asgi.py`).
- `config/settings/production.py`: Entorno estricto para el VPS Linux con validaciones de seguridad y requerimiento obligatorio de PostgreSQL.

---

## 2. Variables de Entorno

### 2.1 Carga y Prioridad
1. **Variables del proceso (Sistema Operativo / Servicio / Gunicorn / systemd):** Tienen **prioridad absoluta**.
2. **Archivo `.env` en la raíz del proyecto:** Se carga mediante `python-dotenv` con la directiva `override=False`. Esto significa que si una variable ya fue exportada por el sistema o la sesión shell, el valor del archivo `.env` **no sobrescribirá** la variable del proceso.
3. Si el archivo `.env` no existe (por ejemplo, en un contenedor o servicio donde las variables se inyectan en memoria), el sistema no falla y lee las variables del entorno del sistema.

### 2.2 Diccionario de Variables

| Variable | Tipo | Obligatoria en Dev | Obligatoria en Prod | Descripción / Ejemplo |
| :--- | :--- | :--- | :--- | :--- |
| `DJANGO_SECRET_KEY` | String | No (usa fallback dev) | **Sí** | Clave criptográfica. En producción se prohíbe el prefijo `django-insecure-`. |
| `DJANGO_DEBUG` | Boolean | No (default: True) | **Sí (debe ser False)** | En producción se prohíbe explícitamente `True`. |
| `DJANGO_ALLOWED_HOSTS` | Lista CSV | No (default: `['*']`) | **Sí** | Lista de dominios/IPs (ej. `distribuidora.ejemplo.com,127.0.0.1`). Se prohíbe `*` en producción. |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Lista CSV | No | Opcional / Recomendada | Orígenes completos HTTPS para formularios web (ej. `https://distribuidora.ejemplo.com`). |
| `DB_ENGINE` | String | No (default: `sqlite`) | **Sí (`postgresql`)** | Motor de base de datos. En producción se prohíbe `sqlite`. |
| `DB_NAME` | String | No | **Sí** (si PostgreSQL) | Nombre de la base de datos PostgreSQL. |
| `DB_USER` | String | No | **Sí** (si PostgreSQL) | Usuario de la base de datos PostgreSQL. |
| `DB_PASSWORD` | String | No | **Sí** (si PostgreSQL) | Contraseña del usuario PostgreSQL. |
| `DB_HOST` | String | No | **Sí** (si PostgreSQL) | Host o IP del servidor PostgreSQL (ej. `localhost` o `127.0.0.1`). |
| `DB_PORT` | Entero | No | No (default: `5432`) | Puerto de escucha de PostgreSQL. |
| `DJANGO_SECURE_PROXY_SSL_HEADER` | Boolean | No | Opcional | Si es `True`, activa `HTTP_X_FORWARDED_PROTO = https`. Requiere Nginx configurado. |
| `DJANGO_SECURE_SSL_REDIRECT` | Boolean | No | Opcional | Si es `True`, redirige todas las peticiones HTTP a HTTPS. |

*Compatibilidad hacia atrás:* Se mantiene soporte para los nombres heredados `SECRET_KEY`, `DEBUG` y `ALLOWED_HOSTS` si las variables con prefijo `DJANGO_` no están presentes.

---

## 3. Guía de Uso por Entorno

### 3.1 Entorno de Desarrollo Local (SQLite por defecto)

Por defecto, el proyecto está preparado para funcionar de inmediato en desarrollo sin necesidad de configurar un servidor de base de datos:

1. **Sin archivo `.env`:**
   Al ejecutar `python manage.py runserver` o `python manage.py test`, Django utiliza automáticamente `config.settings.local`, SQLite en `db.sqlite3`, `DEBUG=True` y `ALLOWED_HOSTS=['*']`.

2. **Con archivo `.env` (opcional en desarrollo):**
   Copie `.env.example` como `.env` en la raíz del proyecto para personalizar variables locales:
   ```bash
   cp .env.example .env
   ```

3. **Prueba de PostgreSQL en Desarrollo Local:**
   Si dispone de un PostgreSQL local y desea probar contra él en desarrollo:
   ```env
   DB_ENGINE=postgresql
   DB_NAME=jcdistribuciones_dev
   DB_USER=postgres
   DB_PASSWORD=mi_clave_local
   DB_HOST=localhost
   DB_PORT=5432
   ```

### 3.2 Entorno de Producción en VPS Linux (PostgreSQL)

Para ejecutar en producción, debe seleccionarse explícitamente el módulo de settings de producción:

```bash
export DJANGO_SETTINGS_MODULE=config.settings.production
```

O al invocar Gunicorn / systemd:
```bash
gunicorn config.wsgi:application --env DJANGO_SETTINGS_MODULE=config.settings.production ...
```

#### Validaciones que Bloquean el Arranque en Producción:
El archivo `config/settings/production.py` detendrá el arranque con un error descriptivo (`ImproperlyConfigured`) si:
- `DJANGO_DEBUG` o `DEBUG` está configurado en `True`.
- `DJANGO_SECRET_KEY` está vacía o utiliza la clave insegura predeterminada.
- `DJANGO_ALLOWED_HOSTS` está vacío o contiene el comodín `'*'`.
- `DB_ENGINE` no está configurado como `postgresql` (intento de usar SQLite o ausencia de motor).
- Falta alguna de las credenciales obligatorias de PostgreSQL (`DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`).

---

## 4. Matriz Comparativa: Desarrollo vs Producción

| Característica | Desarrollo (`local.py`) | Producción (`production.py`) |
| :--- | :--- | :--- |
| **DEBUG** | `True` por defecto | `False` obligatorio (inmutable) |
| **ALLOWED_HOSTS** | `['*']` por defecto | Lista estricta sin comodín `*` |
| **SECRET_KEY** | Clave de desarrollo permitida | Clave secreta robusta obligatoria |
| **Base de Datos** | SQLite (`db.sqlite3`) o PostgreSQL | **PostgreSQL obligatorio** (SQLite prohibido) |
| **Fallback de DB** | Si falla PostgreSQL, se reporta error | Sin fallback; aborta ante variables incompletas |
| **Cookies de Sesión y CSRF** | Estándar HTTP | `Secure=True`, `HttpOnly=True` |
| **Cabeceras de Seguridad** | Estándar | `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY` |

---

## 5. Aclaración Crítica sobre Migración de Datos

> [!CAUTION]
> **Cambiar `DB_ENGINE` o modificar `DATABASES` NO transfiere automáticamente los datos existentes de SQLite a PostgreSQL.**
> Al cambiar el motor a PostgreSQL, la base de datos estará inicialmente vacía. El traspaso de datos históricos requiere un procedimiento ETL específico (Fase de Migración / Tarea DIST-006).

---

## 6. Verificaciones y Condiciones Pendientes en el VPS

Antes de habilitar el tráfico público en el VPS Linux, deberán validarse en el servidor:
1. **Configuración de Nginx:**
   - Asegurarse de que Nginx elimine cualquier cabecera `X-Forwarded-Proto` enviada por clientes externos y solo la inyecte cuando la conexión SSL termine legítimamente en Nginx (`proxy_set_header X-Forwarded-Proto $scheme;`).
   - Solo tras verificar esto, podrá activarse `DJANGO_SECURE_PROXY_SSL_HEADER=True`.
2. **Certificado SSL / HTTPS:**
   - Emitir certificado (Let's Encrypt / Certbot) para el dominio oficial antes de habilitar `DJANGO_SECURE_SSL_REDIRECT=True`.
3. **Servicio Systemd y Gunicorn:**
   - Configurar el daemon de Gunicorn con variables de entorno protegidas y permisos de lectura restringidos (`chmod 600 .env`).
4. **Prueba de Conexión PostgreSQL:**
   - Ejecutar `python manage.py check --settings=config.settings.production` en el VPS una vez creado el usuario y la base de datos en PostgreSQL.
