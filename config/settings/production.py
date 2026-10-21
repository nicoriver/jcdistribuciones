import os
from django.core.exceptions import ImproperlyConfigured
from .base import *

# ------------------------------------------------------------------------------
# 1. Validación Estricta de DEBUG en Producción
# ------------------------------------------------------------------------------
if get_bool_env('DJANGO_DEBUG', get_bool_env('DEBUG', False)):
    raise ImproperlyConfigured(
        "DJANGO_DEBUG / DEBUG=True no está permitido en el entorno de producción."
    )
DEBUG = False

# ------------------------------------------------------------------------------
# 2. Validación Estricta de SECRET_KEY
# ------------------------------------------------------------------------------
prod_secret_key = os.environ.get('DJANGO_SECRET_KEY') or os.environ.get('SECRET_KEY')
if not prod_secret_key:
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY es obligatoria en el entorno de producción."
    )
if prod_secret_key.startswith('django-insecure-'):
    raise ImproperlyConfigured(
        "No se permite utilizar la clave insegura predeterminada de desarrollo en producción. "
        "Defina una clave criptográficamente segura en DJANGO_SECRET_KEY."
    )
SECRET_KEY = prod_secret_key

# ------------------------------------------------------------------------------
# 3. Validación Estricta de ALLOWED_HOSTS
# ------------------------------------------------------------------------------
prod_allowed_hosts = get_list_env('DJANGO_ALLOWED_HOSTS', get_list_env('ALLOWED_HOSTS', []))
if not prod_allowed_hosts:
    raise ImproperlyConfigured(
        "DJANGO_ALLOWED_HOSTS debe contener al menos un dominio o IP explícito en producción."
    )
if '*' in prod_allowed_hosts:
    raise ImproperlyConfigured(
        "No se permite el comodín '*' en DJANGO_ALLOWED_HOSTS en el entorno de producción."
    )
ALLOWED_HOSTS = prod_allowed_hosts

# ------------------------------------------------------------------------------
# 4. Orígenes de Confianza CSRF (HTTPS)
# ------------------------------------------------------------------------------
CSRF_TRUSTED_ORIGINS = get_list_env(
    'DJANGO_CSRF_TRUSTED_ORIGINS',
    get_list_env('CSRF_TRUSTED_ORIGINS', [])
)

# ------------------------------------------------------------------------------
# 5. Base de Datos en Producción: PostgreSQL Obligatorio (Prohíbe SQLite)
# ------------------------------------------------------------------------------
DATABASES = build_database_config(is_production=True)

# ------------------------------------------------------------------------------
# 6. Seguridad de Cookies y Cabeceras Web
# ------------------------------------------------------------------------------
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# ------------------------------------------------------------------------------
# 7. Reverse Proxy y Redirección HTTPS
# ------------------------------------------------------------------------------
# NOTA CRÍTICA DE SEGURIDAD:
# No activar SECURE_PROXY_SSL_HEADER hasta que Nginx esté debidamente configurado
# para eliminar o sobreescribir cabeceras X-Forwarded-Proto no confiables
# provenientes de clientes externos.
if get_bool_env('DJANGO_SECURE_PROXY_SSL_HEADER', False):
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

if get_bool_env('DJANGO_SECURE_SSL_REDIRECT', False):
    SECURE_SSL_REDIRECT = True
