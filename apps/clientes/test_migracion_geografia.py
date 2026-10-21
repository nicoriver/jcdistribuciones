"""
Pruebas de regresión y portabilidad para la migración geográfica de clientes (DIST-003B).
Valida apps/clientes/migrations/0002_remove_localidad_provincia_alter_cliente_localidad_and_more.py
utilizando bases de datos SQLite temporales y descartables, sin alterar la base de datos principal.
"""

import os
import tempfile
from unittest import TestCase
from decimal import Decimal
from django.core.management import call_command
from django.db import connection, connections
from django.test import override_settings


class MigracionGeografiaClientesTests(TestCase):

    def setUp(self):
        super().setUp()
        self.temp_file = tempfile.NamedTemporaryFile(suffix='.sqlite3', delete=False)
        self.temp_file.close()
        self.db_alias = f"test_geo_{id(self)}_{os.getpid()}"

        connections.databases[self.db_alias] = {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': self.temp_file.name,
            'ATOMIC_REQUESTS': False,
            'AUTOCOMMIT': True,
            'OPTIONS': {},
            'TIME_ZONE': None,
            'CONN_MAX_AGE': 0,
            'CONN_HEALTH_CHECKS': False,
        }
        self.conn = connections[self.db_alias]

    def tearDown(self):
        try:
            if self.db_alias in connections:
                connections[self.db_alias].close()
                del connections[self.db_alias]
        finally:
            if self.db_alias in connections.databases:
                del connections.databases[self.db_alias]
            if os.path.exists(self.temp_file.name):
                try:
                    os.remove(self.temp_file.name)
                except OSError:
                    pass
        super().tearDown()

    def test_migracion_desde_cero(self):
        """
        Verifica que la migración se aplique limpiamente desde cero en una base vacía.
        """
        # Ejecutar todas las migraciones hasta clientes 0002
        call_command('migrate', 'clientes', '0002', database=self.db_alias, verbosity=0)

        with self.conn.cursor() as cursor:
            tables = [t.lower() for t in self.conn.introspection.table_names(cursor)]

        # Tablas destino deben existir
        self.assertIn('geografia_provincia', tables)
        self.assertIn('geografia_zona', tables)
        self.assertIn('geografia_localidad', tables)

        # Tablas antiguas deben haber sido eliminadas por clientes.0002
        self.assertNotIn('clientes_provincia', tables)
        self.assertNotIn('clientes_zona', tables)
        self.assertNotIn('clientes_localidad', tables)

    def test_migracion_con_datos_relacionados(self):
        """
        Verifica que se conserven IDs, datos y claves foráneas de provincia, zona,
        localidad, cliente y asignación de zona a vendedor.
        """
        # 1. Migrar hasta el estado previo (clientes 0001 y geografia 0001)
        call_command('migrate', 'usuarios', database=self.db_alias, verbosity=0)
        call_command('migrate', 'productos', '0001', database=self.db_alias, verbosity=0)
        call_command('migrate', 'clientes', '0001', database=self.db_alias, verbosity=0)
        call_command('migrate', 'geografia', '0001', database=self.db_alias, verbosity=0)

        # 2. Insertar datos en las tablas antiguas y modelos relacionados
        with self.conn.cursor() as cursor:
            # Usuario para Cliente
            cursor.execute(
                "INSERT INTO usuarios_usuario (id, password, is_superuser, username, email, nombre, apellido, rol, is_active, is_staff, date_joined) "
                "VALUES (1, 'pbkdf2_test', 0, 'cli_user', 'cli@test.com', 'Cliente', 'Test', 'CLIENTE', 1, 0, '2026-01-01 00:00:00')"
            )
            # Condicion IVA
            cursor.execute(
                "INSERT INTO clientes_condicioniva (id, codigo, descripcion, discrimina_iva) "
                "VALUES (1, 'RI', 'Responsable Inscripto', 1)"
            )
            # Provincia antigua
            cursor.execute(
                "INSERT INTO clientes_provincia (id, nombre) VALUES (5, 'Santa Fe')"
            )
            # Zona antigua
            cursor.execute(
                "INSERT INTO clientes_zona (id, nombre, descripcion) VALUES (12, 'Zona Litoral', 'Distribución costera')"
            )
            # Localidad antigua
            cursor.execute(
                "INSERT INTO clientes_localidad (id, provincia_id, nombre, codigo_postal) "
                "VALUES (50, 5, 'Rosario', '2000')"
            )
            # Vendedor
            cursor.execute(
                "INSERT INTO clientes_vendedor (id, nombre, apellido, dni, telefono, comision_porcentaje, activo) "
                "VALUES (1, 'Juan', 'Pérez', '20123456', '341-5551234', 3.50, 1)"
            )
            # AsignacionZonaVendedor
            cursor.execute(
                "INSERT INTO clientes_asignacionzonavendedor (id, vendedor_id, zona_id, activo, fecha_asignacion, observaciones) "
                "VALUES (1, 1, 12, 1, '2026-01-01 10:00:00', 'Asignación inicial')"
            )
            # Cliente
            cursor.execute(
                "INSERT INTO clientes_cliente ("
                "   id, razon_social, nombre_fantasia, cuit, domicilio, dia_reparto, telefono, email, "
                "   latitud, longitud, estado, monto_minimo_pedido, lista_precio_default_id, "
                "   usuario_id, condicion_iva_id, localidad_id, vendedor_id, zona_id"
                ") VALUES ("
                "   1, 'Almacén Don Pepe', 'Don Pepe', '20123456789', 'San Martín 1234', 1, '341-4445555', "
                "   'pepe@test.com', NULL, NULL, 'ACTIVO', 0.0, NULL, 1, 1, 50, 1, 12"
                ")"
            )

        # 3. Aplicar clientes 0002
        call_command('migrate', 'clientes', '0002', database=self.db_alias, verbosity=0)

        # 4. Verificar datos copiados en geografia
        with self.conn.cursor() as cursor:
            # Provincia
            cursor.execute("SELECT id, nombre FROM geografia_provincia WHERE id = 5")
            prov = cursor.fetchone()
            self.assertIsNotNone(prov)
            self.assertEqual(prov[0], 5)
            self.assertEqual(prov[1], 'Santa Fe')

            # Zona
            cursor.execute("SELECT id, nombre, descripcion, activa FROM geografia_zona WHERE id = 12")
            zona = cursor.fetchone()
            self.assertIsNotNone(zona)
            self.assertEqual(zona[0], 12)
            self.assertEqual(zona[1], 'Zona Litoral')
            self.assertEqual(zona[2], 'Distribución costera')
            self.assertEqual(zona[3], 1)

            # Localidad
            cursor.execute("SELECT id, provincia_id, nombre, codigo_postal FROM geografia_localidad WHERE id = 50")
            loc = cursor.fetchone()
            self.assertIsNotNone(loc)
            self.assertEqual(loc[0], 50)
            self.assertEqual(loc[1], 5)
            self.assertEqual(loc[2], 'Rosario')
            self.assertEqual(loc[3], '2000')

            # Cliente conserva relaciones hacia los nuevos modelos manteniendo IDs
            cursor.execute("SELECT id, localidad_id, zona_id FROM clientes_cliente WHERE id = 1")
            cli = cursor.fetchone()
            self.assertIsNotNone(cli)
            self.assertEqual(cli[1], 50)  # FK a geografia_localidad
            self.assertEqual(cli[2], 12)  # FK a geografia_zona

            # AsignacionZonaVendedor conserva FK a geografia_zona
            cursor.execute("SELECT id, zona_id FROM clientes_asignacionzonavendedor WHERE id = 1")
            asig = cursor.fetchone()
            self.assertIsNotNone(asig)
            self.assertEqual(asig[1], 12)

    def test_idempotencia_segunda_ejecucion(self):
        """
        Verifica que si los datos ya fueron migrados de forma idéntica, la función
        no duplica ni falla al ejecutarse nuevamente.
        """
        call_command('migrate', 'usuarios', database=self.db_alias, verbosity=0)
        call_command('migrate', 'productos', '0001', database=self.db_alias, verbosity=0)
        call_command('migrate', 'clientes', '0001', database=self.db_alias, verbosity=0)
        call_command('migrate', 'geografia', '0001', database=self.db_alias, verbosity=0)

        with self.conn.cursor() as cursor:
            cursor.execute("INSERT INTO clientes_provincia (id, nombre) VALUES (1, 'Buenos Aires')")
            # Ya existente en destino con los mismos datos
            cursor.execute("INSERT INTO geografia_provincia (id, nombre) VALUES (1, 'Buenos Aires')")

        # Debe completarse sin error
        call_command('migrate', 'clientes', '0002', database=self.db_alias, verbosity=0)

        with self.conn.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM geografia_provincia WHERE id = 1")
            count = cursor.fetchone()[0]
            self.assertEqual(count, 1)

    def test_conflicto_id_con_datos_distintos(self):
        """
        Verifica que si en destino existe el mismo ID pero con nombre distinto,
        aborte con RuntimeError explícito.
        """
        call_command('migrate', 'usuarios', database=self.db_alias, verbosity=0)
        call_command('migrate', 'productos', '0001', database=self.db_alias, verbosity=0)
        call_command('migrate', 'clientes', '0001', database=self.db_alias, verbosity=0)
        call_command('migrate', 'geografia', '0001', database=self.db_alias, verbosity=0)

        with self.conn.cursor() as cursor:
            cursor.execute("INSERT INTO clientes_provincia (id, nombre) VALUES (1, 'Buenos Aires')")
            cursor.execute("INSERT INTO geografia_provincia (id, nombre) VALUES (1, 'Córdoba')")

        with self.assertRaises(RuntimeError) as ctx:
            call_command('migrate', 'clientes', '0002', database=self.db_alias, verbosity=0)

        self.assertIn("ya existe en 'geografia_provincia' con nombre 'Córdoba', distinto del origen 'Buenos Aires'", str(ctx.exception))

    def test_conflicto_nombre_unico_con_id_distinto(self):
        """
        Verifica que si en destino existe el mismo nombre único pero con ID distinto,
        aborte con RuntimeError descriptivo en lugar de corromper relaciones.
        """
        call_command('migrate', 'usuarios', database=self.db_alias, verbosity=0)
        call_command('migrate', 'productos', '0001', database=self.db_alias, verbosity=0)
        call_command('migrate', 'clientes', '0001', database=self.db_alias, verbosity=0)
        call_command('migrate', 'geografia', '0001', database=self.db_alias, verbosity=0)

        with self.conn.cursor() as cursor:
            cursor.execute("INSERT INTO clientes_provincia (id, nombre) VALUES (2, 'Santa Fe')")
            cursor.execute("INSERT INTO geografia_provincia (id, nombre) VALUES (1, 'Santa Fe')")

        with self.assertRaises(RuntimeError) as ctx:
            call_command('migrate', 'clientes', '0002', database=self.db_alias, verbosity=0)

        self.assertIn("incompatible con el ID de origen 2", str(ctx.exception))

    def test_evaluacion_reversibilidad_documentada(self):
        """
        Evalúa y documenta que clientes.0002 elimina permanentemente los modelos
        clientes_provincia, clientes_zona y clientes_localidad, por lo que su rollback
        no es intrínsecamente seguro para recuperar datos históricos.
        """
        import importlib
        mig_0002 = importlib.import_module(
            'apps.clientes.migrations.0002_remove_localidad_provincia_alter_cliente_localidad_and_more'
        )

        # La primera operación es RunPython con reverse_code noop
        first_op = mig_0002.Migration.operations[0]
        self.assertEqual(first_op.reverse_code, mig_0002.migrations.RunPython.noop)
