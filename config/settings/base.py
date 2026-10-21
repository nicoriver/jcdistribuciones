from pathlib import Path
import os
import sys
from dotenv import load_dotenv
from django.core.exceptions import ImproperlyConfigured

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# ------------------------------------------------------------------------------
# 1. Carga de Variables de Entorno (python-dotenv)
# ------------------------------------------------------------------------------
# Se busca un archivo .env en la raíz del proyecto.
# override=False garantiza que las variables del proceso tengan prioridad absoluta.
ENV_FILE = BASE_DIR / '.env'
if ENV_FILE.exists():
    load_dotenv(dotenv_path=ENV_FILE, override=False)

# Agregar el directorio apps/ a sys.path
sys.path.insert(0, os.path.join(BASE_DIR, 'apps'))


# ------------------------------------------------------------------------------
# 2. Funciones auxiliares de parseo seguro
# ------------------------------------------------------------------------------
def get_bool_env(name, default=False):
    """
    Parsea variables de entorno booleanas sin incurrir en el error bool("False") == True.
    Acepta: 'true', '1', 'yes', 't', 'on' (case insensitive) como True.
    """
    val = os.environ.get(name)
    if val is None:
        return default
    return str(val).strip().lower() in ('true', '1', 'yes', 't', 'on')


def get_list_env(name, default=None):
    """
    Parsea variables de entorno separadas por comas en una lista de cadenas no vacías.
    """
    val = os.environ.get(name)
    if val is None:
        return list(default) if default is not None else []
    return [item.strip() for item in str(val).split(',') if item.strip()]


# ------------------------------------------------------------------------------
# 3. Función constructora de configuración de Base de Datos
# ------------------------------------------------------------------------------
def build_database_config(is_production=False):
    """
    Construye el diccionario DATABASES según las variables de entorno:
    - En desarrollo (is_production=False): SQLite es la opción por defecto.
      Permite seleccionar PostgreSQL explícitamente si se configura DB_ENGINE.
    - En producción (is_production=True): Se prohíbe SQLite y se exige PostgreSQL
      con todos sus parámetros de conexión validados.
    - Rechaza motores no reconocidos con ImproperlyConfigured.
    - No realiza conexiones a la base de datos durante la configuración.
    """
    engine_raw = os.environ.get('DB_ENGINE', '').strip().lower()

    # Si no se especificó motor
    if not engine_raw:
        if is_production:
            raise ImproperlyConfigured(
                "En el entorno de producción es obligatorio definir DB_ENGINE=postgresql."
            )
        return {
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': BASE_DIR / 'db.sqlite3',
            }
        }

    # SQLite
    if engine_raw in ('sqlite', 'sqlite3', 'django.db.backends.sqlite3'):
        if is_production:
            raise ImproperlyConfigured(
                "El uso de SQLite no está permitido en el entorno de producción. "
                "Debe configurar DB_ENGINE=postgresql y las credenciales correspondientes."
            )
        return {
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': BASE_DIR / 'db.sqlite3',
            }
        }

    # PostgreSQL
    if engine_raw in ('postgresql', 'postgres', 'django.db.backends.postgresql'):
        required_vars = ['DB_NAME', 'DB_USER', 'DB_PASSWORD', 'DB_HOST']
        missing = [var for var in required_vars if not os.environ.get(var, '').strip()]
        if missing:
            raise ImproperlyConfigured(
                f"Faltan variables obligatorias para la configuración de PostgreSQL: {', '.join(missing)}. "
                "No se permite fallback silencioso a SQLite."
            )

        port_raw = os.environ.get('DB_PORT', '5432').strip() or '5432'
        try:
            port = int(port_raw)
        except ValueError:
            raise ImproperlyConfigured(
                f"El valor de DB_PORT no es un puerto numérico válido: '{port_raw}'."
            )

        return {
            'default': {
                'ENGINE': 'django.db.backends.postgresql',
                'NAME': os.environ['DB_NAME'].strip(),
                'USER': os.environ['DB_USER'].strip(),
                'PASSWORD': os.environ['DB_PASSWORD'],
                'HOST': os.environ['DB_HOST'].strip(),
                'PORT': port,
            }
        }

    # Motor no soportado
    raise ImproperlyConfigured(
        f"Motor de base de datos no soportado o desconocido en DB_ENGINE: '{engine_raw}'. "
        "Valores permitidos: 'sqlite' (solo desarrollo) o 'postgresql'."
    )


# ------------------------------------------------------------------------------
# 4. Parámetros Base de Django
# ------------------------------------------------------------------------------
SECRET_KEY = (
    os.environ.get('DJANGO_SECRET_KEY')
    or os.environ.get('SECRET_KEY')
    or 'django-insecure-base-key-jcdistribuciones'
)

DEBUG = get_bool_env('DJANGO_DEBUG', get_bool_env('DEBUG', True))

ALLOWED_HOSTS = get_list_env('DJANGO_ALLOWED_HOSTS', get_list_env('ALLOWED_HOSTS', []))

CSRF_TRUSTED_ORIGINS = get_list_env(
    'DJANGO_CSRF_TRUSTED_ORIGINS',
    get_list_env('CSRF_TRUSTED_ORIGINS', [])
)

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Local Apps
    'usuarios.apps.UsuariosConfig',
    'geografia.apps.GeografiaConfig',
    'proveedores.apps.ProveedoresConfig',
    'clientes.apps.ClientesConfig',
    'productos.apps.ProductosConfig',
    'pedidos.apps.PedidosConfig',
    'portal.apps.PortalConfig',
    'stock.apps.StockConfig',
    'compras.apps.ComprasConfig',
    'comprobantes.apps.ComprobantesConfig',
    'reportes.apps.ReportesConfig',
    'gestion.apps.GestionConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

# Database (por defecto en base: SQLite para desarrollo)
DATABASES = build_database_config(is_production=False)

# Custom User Model
AUTH_USER_MODEL = 'usuarios.Usuario'

# Authentication Backends (Login dual por CUIT/DNI, Username o Email)
AUTHENTICATION_BACKENDS = [
    'usuarios.backends.DualAuthBackend',
    'django.contrib.auth.backends.ModelBackend',
]

LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/login/'

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'es-ar'
TIME_ZONE = 'America/Argentina/Buenos_Aires'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
