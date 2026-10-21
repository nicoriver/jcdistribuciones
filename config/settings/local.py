from .base import *

# Modo Debug en desarrollo local (True por defecto, configurable por entorno)
DEBUG = get_bool_env('DJANGO_DEBUG', get_bool_env('DEBUG', True))

# En desarrollo local se permite '*' por defecto si no se especifican hosts
ALLOWED_HOSTS = get_list_env('DJANGO_ALLOWED_HOSTS', get_list_env('ALLOWED_HOSTS', ['*']))

# Base de datos en desarrollo: SQLite por defecto o PostgreSQL si se indicó en entorno
DATABASES = build_database_config(is_production=False)
