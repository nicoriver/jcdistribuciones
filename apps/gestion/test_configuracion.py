import os
import sys
import tempfile
import importlib
from unittest import TestCase
from unittest.mock import patch
from django.core.exceptions import ImproperlyConfigured
from config.settings.base import build_database_config, get_bool_env, get_list_env, BASE_DIR
from dotenv import load_dotenv


class ConfiguracionEntornoTests(TestCase):
    """
    Pruebas unitarias de configuración y selección de entornos (DIST-002).
    Aisladas, puras y sin conexiones a bases de datos ni servicios externos.
    """

    def test_sqlite_seleccion_desarrollo_por_defecto(self):
        """Verifica que sin DB_ENGINE, en desarrollo se selecciona SQLite por defecto."""
        with patch.dict(os.environ, {}, clear=True):
            config = build_database_config(is_production=False)
            self.assertEqual(config['default']['ENGINE'], 'django.db.backends.sqlite3')
            self.assertEqual(config['default']['NAME'], BASE_DIR / 'db.sqlite3')

    def test_sqlite_seleccion_desarrollo_explicita(self):
        """Verifica que DB_ENGINE=sqlite en desarrollo selecciona SQLite correctamente."""
        with patch.dict(os.environ, {'DB_ENGINE': 'sqlite'}, clear=True):
            config = build_database_config(is_production=False)
            self.assertEqual(config['default']['ENGINE'], 'django.db.backends.sqlite3')
            self.assertEqual(config['default']['NAME'], BASE_DIR / 'db.sqlite3')

    def test_postgresql_construccion_con_valores_ficticios(self):
        """Verifica la construcción de la configuración de PostgreSQL con valores ficticios."""
        mock_env = {
            'DB_ENGINE': 'postgresql',
            'DB_NAME': 'jcdistribuciones_test',
            'DB_USER': 'test_user',
            'DB_PASSWORD': 'dummy_secret_password',
            'DB_HOST': '127.0.0.1',
            'DB_PORT': '5432',
        }
        with patch.dict(os.environ, mock_env, clear=True):
            config = build_database_config(is_production=False)
            self.assertEqual(config['default']['ENGINE'], 'django.db.backends.postgresql')
            self.assertEqual(config['default']['NAME'], 'jcdistribuciones_test')
            self.assertEqual(config['default']['USER'], 'test_user')
            self.assertEqual(config['default']['PASSWORD'], 'dummy_secret_password')
            self.assertEqual(config['default']['HOST'], '127.0.0.1')
            self.assertEqual(config['default']['PORT'], 5432)

    def test_rechazo_motor_desconocido(self):
        """Verifica que un motor desconocido lance ImproperlyConfigured."""
        with patch.dict(os.environ, {'DB_ENGINE': 'oracle'}, clear=True):
            with self.assertRaises(ImproperlyConfigured) as ctx:
                build_database_config(is_production=False)
            self.assertIn("Motor de base de datos no soportado", str(ctx.exception))

    def test_rechazo_sqlite_en_produccion(self):
        """Verifica que el uso de SQLite en producción sea rechazado."""
        with patch.dict(os.environ, {'DB_ENGINE': 'sqlite'}, clear=True):
            with self.assertRaises(ImproperlyConfigured) as ctx:
                build_database_config(is_production=True)
            self.assertIn("SQLite no está permitido en el entorno de producción", str(ctx.exception))

        # También si no se especifica DB_ENGINE en producción
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ImproperlyConfigured) as ctx:
                build_database_config(is_production=True)
            self.assertIn("obligatorio definir DB_ENGINE=postgresql", str(ctx.exception))

    def test_errores_por_variables_obligatorias_ausentes(self):
        """Verifica que falten variables requeridas de PostgreSQL sin revelar secretos."""
        mock_env = {
            'DB_ENGINE': 'postgresql',
            'DB_NAME': 'jcdistribuciones_prod',
            # Falta DB_USER, DB_PASSWORD, DB_HOST
        }
        with patch.dict(os.environ, mock_env, clear=True):
            with self.assertRaises(ImproperlyConfigured) as ctx:
                build_database_config(is_production=False)
            msg = str(ctx.exception)
            self.assertIn("Faltan variables obligatorias", msg)
            self.assertIn("DB_USER", msg)
            self.assertIn("DB_PASSWORD", msg)
            self.assertIn("DB_HOST", msg)
            # Asegura que no se expongan valores
            self.assertNotIn("jcdistribuciones_prod", msg)

    def test_interpretacion_correcta_debug_bool(self):
        """Verifica que get_bool_env no incurra en el error bool('False') == True."""
        cases = [
            ('False', False),
            ('false', False),
            ('0', False),
            ('no', False),
            ('off', False),
            ('True', True),
            ('true', True),
            ('1', True),
            ('yes', True),
            ('on', True),
            ('', False),
        ]
        for val, expected in cases:
            with patch.dict(os.environ, {'TEST_VAR': val}):
                self.assertEqual(get_bool_env('TEST_VAR'), expected, f"Fallo al evaluar {val}")

    def test_prioridad_entorno_proceso_frente_a_dotenv(self):
        """Verifica que load_dotenv(override=False) no sobreescriba variables del proceso."""
        with tempfile.NamedTemporaryFile('w', delete=False, suffix='.env') as tmp_file:
            tmp_file.write("MI_VARIABLE_TEST=valor_desde_archivo\n")
            tmp_path = tmp_file.name

        try:
            with patch.dict(os.environ, {'MI_VARIABLE_TEST': 'valor_proceso_prioritario'}):
                load_dotenv(dotenv_path=tmp_path, override=False)
                self.assertEqual(os.environ.get('MI_VARIABLE_TEST'), 'valor_proceso_prioritario')
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_parseo_listas_csv(self):
        """Verifica el parseo correcto de listas separadas por coma."""
        with patch.dict(os.environ, {'TEST_HOSTS': 'example.com, test.com,   127.0.0.1  '}):
            hosts = get_list_env('TEST_HOSTS')
            self.assertEqual(hosts, ['example.com', 'test.com', '127.0.0.1'])

    def test_produccion_valida_correctamente_con_entorno_completo(self):
        """Verifica que production.py cargue correctamente con variables de producción válidas."""
        mock_env = {
            'DJANGO_SECRET_KEY': 'prod-strong-secret-key-1234567890-test',
            'DJANGO_DEBUG': 'False',
            'DJANGO_ALLOWED_HOSTS': 'distribuidora.ejemplo.com',
            'DJANGO_CSRF_TRUSTED_ORIGINS': 'https://distribuidora.ejemplo.com',
            'DB_ENGINE': 'postgresql',
            'DB_NAME': 'jcdistribuciones_prod',
            'DB_USER': 'prod_user',
            'DB_PASSWORD': 'prod_secret_password',
            'DB_HOST': '127.0.0.1',
            'DB_PORT': '5432',
        }
        with patch.dict(os.environ, mock_env, clear=True):
            sys.modules.pop('config.settings.production', None)
            prod_settings = importlib.import_module('config.settings.production')
            self.assertFalse(prod_settings.DEBUG)
            self.assertEqual(prod_settings.ALLOWED_HOSTS, ['distribuidora.ejemplo.com'])
            self.assertTrue(prod_settings.SESSION_COOKIE_SECURE)
            self.assertTrue(prod_settings.CSRF_COOKIE_SECURE)
            self.assertEqual(prod_settings.DATABASES['default']['ENGINE'], 'django.db.backends.postgresql')

    def test_produccion_rechaza_debug_true(self):
        """Verifica que production.py rechace DJANGO_DEBUG=True."""
        mock_env = {
            'DJANGO_SECRET_KEY': 'prod-strong-secret-key-1234567890-test',
            'DJANGO_DEBUG': 'True',
            'DJANGO_ALLOWED_HOSTS': 'distribuidora.ejemplo.com',
            'DB_ENGINE': 'postgresql',
            'DB_NAME': 'jcdistribuciones_prod',
            'DB_USER': 'prod_user',
            'DB_PASSWORD': 'prod_secret_password',
            'DB_HOST': '127.0.0.1',
        }
        with patch.dict(os.environ, mock_env, clear=True):
            sys.modules.pop('config.settings.production', None)
            with self.assertRaises(ImproperlyConfigured) as ctx:
                importlib.import_module('config.settings.production')
            self.assertIn("DEBUG=True no está permitido en el entorno de producción", str(ctx.exception))

    def test_produccion_rechaza_secret_key_insegura(self):
        """Verifica que production.py rechace claves inseguras con prefijo django-insecure-."""
        mock_env = {
            'DJANGO_SECRET_KEY': 'django-insecure-default-key',
            'DJANGO_DEBUG': 'False',
            'DJANGO_ALLOWED_HOSTS': 'distribuidora.ejemplo.com',
            'DB_ENGINE': 'postgresql',
            'DB_NAME': 'jcdistribuciones_prod',
            'DB_USER': 'prod_user',
            'DB_PASSWORD': 'prod_secret_password',
            'DB_HOST': '127.0.0.1',
        }
        with patch.dict(os.environ, mock_env, clear=True):
            sys.modules.pop('config.settings.production', None)
            with self.assertRaises(ImproperlyConfigured) as ctx:
                importlib.import_module('config.settings.production')
            self.assertIn("No se permite utilizar la clave insegura", str(ctx.exception))

    def test_produccion_rechaza_allowed_hosts_wildcard(self):
        """Verifica que production.py rechace comodín '*' en ALLOWED_HOSTS."""
        mock_env = {
            'DJANGO_SECRET_KEY': 'prod-strong-secret-key-1234567890-test',
            'DJANGO_DEBUG': 'False',
            'DJANGO_ALLOWED_HOSTS': '*',
            'DB_ENGINE': 'postgresql',
            'DB_NAME': 'jcdistribuciones_prod',
            'DB_USER': 'prod_user',
            'DB_PASSWORD': 'prod_secret_password',
            'DB_HOST': '127.0.0.1',
        }
        with patch.dict(os.environ, mock_env, clear=True):
            sys.modules.pop('config.settings.production', None)
            with self.assertRaises(ImproperlyConfigured) as ctx:
                importlib.import_module('config.settings.production')
            self.assertIn("No se permite el comodín '*'", str(ctx.exception))
