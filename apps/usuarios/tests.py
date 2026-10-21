from django.test import TestCase, Client
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.models import Group, Permission
from django.urls import reverse
from usuarios.roles import setup_roles_and_permissions

Usuario = get_user_model()


class Modulo1UsuariosRBACTestCase(TestCase):
    """
    Suite de verificación del Módulo 1: Core de Autenticación, Roles (RBAC) y Perfiles.
    """

    def setUp(self):
        # Asegurar inicialización limpia de roles y permisos
        setup_roles_and_permissions()
        self.client = Client()

    def test_creacion_supervisor_y_asignacion_grupo_permisos(self):
        """
        a) Verifica que al crear un usuario SUPERVISOR se le asigne automáticamente
        el grupo 'Supervisor', is_staff=True y todos los permisos operativos requeridos.
        """
        supervisor = Usuario.objects.create_user(
            username='sup_operaciones',
            cuit_dni='20334445556',
            email='supervisor@jcdistribuciones.com',
            nombre='Juan',
            apellido='Supervisor',
            rol='SUPERVISOR',
            password='PasswordSup123!'
        )

        # Verificar banderas básicas
        self.assertTrue(supervisor.is_staff)
        self.assertTrue(supervisor.is_active)
        self.assertEqual(supervisor.rol, 'SUPERVISOR')
        self.assertTrue(supervisor.es_supervisor)

        # Verificar pertenencia al grupo 'Supervisor'
        grupos = [g.name for g in supervisor.groups.all()]
        self.assertIn('Supervisor', grupos)

        # Verificar que herede permisos operativos
        # Remitos / Comprobantes
        self.assertTrue(supervisor.has_perm('comprobantes.add_remito'))
        self.assertTrue(supervisor.has_perm('comprobantes.add_notacreditointerna'))
        # Clientes, Proveedores y Zonas
        self.assertTrue(supervisor.has_perm('clientes.add_cliente'))
        self.assertTrue(supervisor.has_perm('geografia.add_zona'))
        self.assertTrue(supervisor.has_perm('proveedores.add_proveedor'))
        # Catálogo / Precios
        self.assertTrue(supervisor.has_perm('productos.add_producto'))
        self.assertTrue(supervisor.has_perm('productos.add_tipolistaprecio'))
        # Stock
        self.assertTrue(supervisor.has_perm('stock.add_movimientostock'))

    def test_login_dual_cuit_dni_y_username(self):
        """
        b) Verifica el inicio de sesión exitoso tanto por CUIT/DNI (con o sin guiones)
        como por username, utilizando el backend DualAuthBackend con contraseñas seguras PBKDF2.
        """
        cuit_raw = '20-33444555-6'
        cuit_clean = '20334445556'
        password = 'PasswordSegura2026!'

        user = Usuario.objects.create_user(
            username='marcos_deposito',
            cuit_dni=cuit_clean,
            email='marcos@jcdistribuciones.com',
            nombre='Marcos',
            apellido='Pérez',
            rol='SUPERVISOR',
            password=password
        )

        # 1. Login usando Username
        user_auth_user = authenticate(username='marcos_deposito', password=password)
        self.assertIsNotNone(user_auth_user)
        self.assertEqual(user_auth_user.pk, user.pk)

        # 2. Login usando CUIT sin guiones
        user_auth_cuit = authenticate(username=cuit_clean, password=password)
        self.assertIsNotNone(user_auth_cuit)
        self.assertEqual(user_auth_cuit.pk, user.pk)

        # 3. Login usando CUIT con guiones
        user_auth_cuit_guiones = authenticate(username=cuit_raw, password=password)
        self.assertIsNotNone(user_auth_cuit_guiones)
        self.assertEqual(user_auth_cuit_guiones.pk, user.pk)

        # 4. Login usando Email
        user_auth_email = authenticate(username='marcos@jcdistribuciones.com', password=password)
        self.assertIsNotNone(user_auth_email)
        self.assertEqual(user_auth_email.pk, user.pk)

        # 5. Rechazo con contraseña inválida
        user_auth_fallido = authenticate(username=cuit_clean, password='PasswordIncorrecta')
        self.assertIsNone(user_auth_fallido)

    def test_restriccion_roles_no_autorizados(self):
        """
        c) Verifica que usuarios con roles no autorizados (CLIENTE o VENDEDOR) no
        posean permisos operativos de supervisión ni puedan acceder a vistas restringidas.
        """
        cliente_user = Usuario.objects.create_user(
            username='cliente_kiosco',
            cuit_dni='30998877665',
            email='kiosco@test.com',
            nombre='Kiosco',
            apellido='Central',
            rol='CLIENTE',
            password='ClientePassword123'
        )

        vendedor_user = Usuario.objects.create_user(
            username='vendedor_ruta',
            cuit_dni='20443322110',
            email='vendedor@test.com',
            nombre='Roberto',
            apellido='Ruta',
            rol='VENDEDOR',
            password='VendedorPassword123'
        )

        # Verificar que CLIENTE no tenga permisos de emisión de comprobantes ni gestión de stock
        self.assertFalse(cliente_user.is_staff)
        self.assertFalse(cliente_user.has_perm('comprobantes.add_remito'))
        self.assertFalse(cliente_user.has_perm('stock.add_movimientostock'))
        self.assertIn('Cliente', [g.name for g in cliente_user.groups.all()])

        # Verificar que VENDEDOR no tenga permisos de supervisión de stock ni emisión directa
        self.assertFalse(vendedor_user.is_staff)
        self.assertFalse(vendedor_user.has_perm('comprobantes.add_remito'))
        self.assertFalse(vendedor_user.has_perm('stock.add_movimientostock'))
        self.assertIn('Vendedor', [g.name for g in vendedor_user.groups.all()])

        # Verificar restricción HTTP: Cliente intentando acceder al Dashboard de Gestión
        self.client.login(username='cliente_kiosco', password='ClientePassword123')
        resp = self.client.get('/gestion/')
        self.assertEqual(resp.status_code, 403)

        # Verificar que Supervisor sí puede acceder al Dashboard de Gestión
        supervisor = Usuario.objects.create_user(
            username='sup_test',
            cuit_dni='20112233445',
            rol='SUPERVISOR',
            password='SupPassword123'
        )
        self.client.login(username='sup_test', password='SupPassword123')
        resp_sup = self.client.get('/gestion/')
        self.assertEqual(resp_sup.status_code, 200)

    def test_propiedades_compatibilidad(self):
        """
        Verifica que propiedades de compatibilidad como 'cuit' y 'nombre_completo'
        funcionen de forma bidireccional sin romper código legacy.
        """
        u = Usuario.objects.create_user(
            username='test_compat',
            cuit='20778899001',
            nombre_completo='Lucía González',
            rol='VENDEDOR',
            password='TestPass123'
        )

        self.assertEqual(u.cuit_dni, '20778899001')
        self.assertEqual(u.cuit, '20778899001')
        self.assertEqual(u.nombre, 'Lucía')
        self.assertEqual(u.apellido, 'González')
        self.assertEqual(u.nombre_completo, 'Lucía González')

        # Probar modificación vía setters
        u.cuit = '20999999999'
        u.nombre_completo = 'Martín Fierro'
        u.save()

        u.refresh_from_db()
        self.assertEqual(u.cuit_dni, '20999999999')
        self.assertEqual(u.nombre, 'Martín')
        self.assertEqual(u.apellido, 'Fierro')
