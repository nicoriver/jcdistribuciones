"""
Pruebas de comportamiento para la gestión de clientes, productos, zonas y vendedores (DIST-004).
Cubre autenticación, redirección según rol, RBAC, operaciones CRUD, validaciones,
asignación histórica de zonas y preservación estricta del Kardex de stock.
"""

from decimal import Decimal
from django.test import TestCase, Client as HttpClient
from django.urls import reverse

from usuarios.models import Usuario
from clientes.models import Cliente, Vendedor, AsignacionZonaVendedor, CondicionIVA
from geografia.models import Zona, Localidad, Provincia
from productos.models import (
    Producto, Categoria, Marca, TipoListaPrecio, PrecioProducto, AlicuotaIVA
)
from stock.models import MovimientoStock


class GestionMaestrosBehaviorTests(TestCase):
    """
    Suite integral de pruebas funcionales y de seguridad para el módulo de Gestión (DIST-004).
    """

    def setUp(self):
        super().setUp()
        self.client = HttpClient()

        # 1. Usuarios por rol
        self.admin_user = Usuario.objects.create_user(
            username='admin_test',
            cuit_dni='20111111111',
            email='admin@test.com',
            password='AdminPassword123!',
            nombre='Admin',
            apellido='Test',
            rol='ADMIN',
            is_staff=True
        )

        self.supervisor_user = Usuario.objects.create_user(
            username='supervisor_test',
            cuit_dni='20222222222',
            email='supervisor@test.com',
            password='SupervisorPassword123!',
            nombre='Supervisor',
            apellido='Test',
            rol='SUPERVISOR'
        )

        self.vendedor_user = Usuario.objects.create_user(
            username='vendedor_test',
            cuit_dni='20333333333',
            email='vendedor@test.com',
            password='VendedorPassword123!',
            nombre='Vendedor',
            apellido='Test',
            rol='VENDEDOR'
        )

        self.cliente_user = Usuario.objects.create_user(
            username='cliente_test',
            cuit_dni='20444444444',
            email='cliente@test.com',
            password='ClientePassword123!',
            nombre='Cliente',
            apellido='Test',
            rol='CLIENTE'
        )

        self.deposito_user = Usuario.objects.create_user(
            username='deposito_test',
            cuit_dni='20555555555',
            email='deposito@test.com',
            password='DepositoPassword123!',
            nombre='Deposito',
            apellido='Test',
            rol='DEPOSITO'
        )

        self.facturacion_user = Usuario.objects.create_user(
            username='facturacion_test',
            cuit_dni='20666666666',
            email='facturacion@test.com',
            password='FacturacionPassword123!',
            nombre='Facturacion',
            apellido='Test',
            rol='FACTURACION'
        )

        # 2. Datos maestros base
        self.provincia = Provincia.objects.create(nombre='Santa Fe')
        self.localidad = Localidad.objects.create(
            provincia=self.provincia,
            nombre='Rosario',
            codigo_postal='2000'
        )
        self.zona1 = Zona.objects.create(
            nombre='Zona Centro',
            descripcion='Macrocentro de Rosario',
            dia_reparto_defecto='Lunes y Jueves',
            activa=True
        )
        self.zona2 = Zona.objects.create(
            nombre='Zona Norte',
            descripcion='Alberdi y Granadero Baigorria',
            dia_reparto_defecto='Martes y Viernes',
            activa=True
        )

        self.condicion_iva = CondicionIVA.objects.create(
            codigo='RI',
            descripcion='Responsable Inscripto',
            discrimina_iva=True
        )

        self.tipo_lista = TipoListaPrecio.objects.create(
            nombre='Lista Mayorista General',
            descripcion='Precios estándar de distribución',
            activa=True
        )

        self.categoria = Categoria.objects.create(
            nombre='Lácteos y Derivados',
            activa=True
        )

        self.marca = Marca.objects.create(
            nombre='Sancor',
            activa=True
        )

        self.vendedor = Vendedor.objects.create(
            legajo='VEND-001',
            nombre='Carlos',
            apellido='Gómez',
            dni='25123456',
            telefono='341-4567890',
            comision_porcentaje=Decimal('3.50'),
            activo=True,
            usuario=self.vendedor_user
        )
        AsignacionZonaVendedor.objects.create(
            vendedor=self.vendedor,
            zona=self.zona1,
            activo=True
        )

        self.alicuota_obj = AlicuotaIVA.objects.create(
            porcentaje=Decimal('21.00'),
            descripcion='IVA General 21%'
        )

        self.cliente_obj = Cliente.objects.create(
            usuario=self.cliente_user,
            cuit='20444444444',
            razon_social='Cliente Portal Test',
            domicilio='Calle Falsa 123',
            condicion_iva=self.condicion_iva,
            tipo_lista_precio=self.tipo_lista,
            zona=self.zona1,
            vendedor=self.vendedor,
            estado='ACTIVO'
        )

    # --------------------------------------------------------------------------
    # 1. Login y Redirecciones por Rol
    # --------------------------------------------------------------------------

    def test_login_redireccion_admin_y_supervisor_a_gestion(self):
        """Admin y Supervisor deben tener como destino habitual el panel de gestión."""
        # Admin
        resp_admin = self.client.post(reverse('portal:login'), {
            'identificador': 'admin_test',
            'password': 'AdminPassword123!'
        })
        self.assertRedirects(resp_admin, reverse('gestion:dashboard'))

        self.client.logout()

        # Supervisor
        resp_sup = self.client.post(reverse('portal:login'), {
            'identificador': 'supervisor_test',
            'password': 'SupervisorPassword123!'
        })
        self.assertRedirects(resp_sup, reverse('gestion:dashboard'))

    def test_login_redireccion_aislamiento_vendedor_cliente_deposito(self):
        """Vendedor, Cliente y Depósito deben conservar sus destinos y aislamiento."""
        # Vendedor
        resp_vend = self.client.post(reverse('portal:login'), {
            'identificador': 'vendedor_test',
            'password': 'VendedorPassword123!'
        })
        self.assertRedirects(resp_vend, reverse('portal:vendedor_pedidos'))

        self.client.logout()

        # Cliente
        resp_cli = self.client.post(reverse('portal:login'), {
            'identificador': '20444444444',
            'password': 'ClientePassword123!'
        })
        self.assertRedirects(resp_cli, reverse('portal:catalogo'))

        self.client.logout()

        # Depósito
        resp_dep = self.client.post(reverse('portal:login'), {
            'identificador': 'deposito_test',
            'password': 'DepositoPassword123!'
        })
        self.assertRedirects(resp_dep, reverse('gestion:deposito_pedidos'))

    def test_login_respeta_next_valido_y_autorizado(self):
        """Un next autorizado debe ser respetado, mientras que intentos no autorizados se aíslan."""
        # Admin con next a clientes
        resp_admin = self.client.post(f"{reverse('portal:login')}?next=/gestion/clientes/", {
            'identificador': 'admin_test',
            'password': 'AdminPassword123!'
        })
        self.assertRedirects(resp_admin, '/gestion/clientes/')

        self.client.logout()

        # Cliente intentando entrar a /gestion/clientes/ mediante next: debe ser rechazado hacia catalogo
        resp_cli = self.client.post(f"{reverse('portal:login')}?next=/gestion/clientes/", {
            'identificador': '20444444444',
            'password': 'ClientePassword123!'
        })
        self.assertRedirects(resp_cli, reverse('portal:catalogo'))

    # --------------------------------------------------------------------------
    # 2. Control de Permisos y Rechazo de Accesos No Autorizados
    # --------------------------------------------------------------------------

    def test_rechazo_accesos_no_autorizados(self):
        """Clientes y vendedores no pueden acceder a pantallas de gestión por URL directa."""
        urls_gestion = [
            reverse('gestion:clientes_list'),
            reverse('gestion:cliente_crear'),
            reverse('gestion:productos_list'),
            reverse('gestion:producto_crear'),
            reverse('gestion:zonas_list'),
            reverse('gestion:zona_crear'),
            reverse('gestion:vendedores_list'),
            reverse('gestion:vendedor_crear'),
        ]

        # 1. Anónimo -> Redirige a Login
        for url in urls_gestion:
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 302, f"Falló anónimo en {url}")
            self.assertIn('/login/', resp.url)

        # 2. Cliente -> 403 Forbidden
        self.client.force_login(self.cliente_user)
        for url in urls_gestion:
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 403, f"Falló cliente en {url}")

        # 3. Vendedor -> 403 Forbidden
        self.client.force_login(self.vendedor_user)
        for url in urls_gestion:
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 403, f"Falló vendedor en {url}")

    def test_prohibicion_modificar_datos_via_get(self):
        """Las acciones de activación/desactivación rechazan métodos GET devolviendo HTTP 405."""
        self.client.force_login(self.admin_user)
        resp_zona = self.client.get(reverse('gestion:zona_toggle', args=[self.zona1.id]))
        self.assertEqual(resp_zona.status_code, 405)

        resp_vend = self.client.get(reverse('gestion:vendedor_toggle', args=[self.vendedor.id]))
        self.assertEqual(resp_vend.status_code, 405)

    def test_permisos_roles_afectados(self):
        """
        ADMIN y SUPERVISOR tienen acceso a Zonas y Vendedores.
        FACTURACION tiene acceso a Clientes y Productos, pero es rechazado (403) en Zonas y Vendedores.
        """
        # FACTURACION: permitido en clientes y productos
        self.client.force_login(self.facturacion_user)
        self.assertEqual(self.client.get(reverse('gestion:clientes_list')).status_code, 200)
        self.assertEqual(self.client.get(reverse('gestion:productos_list')).status_code, 200)

        # FACTURACION: prohibido (403) en zonas y vendedores
        urls_admin_only = [
            reverse('gestion:zonas_list'),
            reverse('gestion:zona_crear'),
            reverse('gestion:vendedores_list'),
            reverse('gestion:vendedor_crear'),
            reverse('gestion:zona_toggle', args=[self.zona1.id]),
            reverse('gestion:vendedor_toggle', args=[self.vendedor.id]),
        ]
        for url in urls_admin_only:
            resp = self.client.post(url, {})
            self.assertEqual(resp.status_code, 403, f"FACTURACION no debe acceder a {url}")

        # SUPERVISOR y ADMIN: permitidos
        self.client.force_login(self.supervisor_user)
        self.assertEqual(self.client.get(reverse('gestion:zonas_list')).status_code, 200)
        self.assertEqual(self.client.get(reverse('gestion:vendedores_list')).status_code, 200)

    # --------------------------------------------------------------------------
    # 3. Gestión de Zonas
    # --------------------------------------------------------------------------

    def test_gestion_zonas_crud_y_toggle(self):
        """Prueba listado, alta, edición, validación de duplicados y toggle de Zonas."""
        self.client.force_login(self.supervisor_user)

        # GET Listado
        resp_list = self.client.get(reverse('gestion:zonas_list'))
        self.assertEqual(resp_list.status_code, 200)
        self.assertContains(resp_list, 'Zona Centro')

        # GET Form Alta
        resp_get_crear = self.client.get(reverse('gestion:zona_crear'))
        self.assertEqual(resp_get_crear.status_code, 200)

        # POST Alta Válida
        resp_crear = self.client.post(reverse('gestion:zona_crear'), {
            'nombre': 'Zona Sur Costera',
            'descripcion': 'Área sur del puerto',
            'dia_reparto_defecto': 'Miércoles',
            'activa': True
        })
        self.assertRedirects(resp_crear, reverse('gestion:zonas_list'))
        self.assertTrue(Zona.objects.filter(nombre='Zona Sur Costera').exists())

        # POST Duplicado -> Rechazado con error
        resp_duplicado = self.client.post(reverse('gestion:zona_crear'), {
            'nombre': 'Zona Sur Costera',
            'descripcion': 'Otra',
            'dia_reparto_defecto': 'Miércoles',
            'activa': True
        })
        self.assertEqual(resp_duplicado.status_code, 200)
        self.assertContains(resp_duplicado, 'Ya existe una zona registrada con el nombre')

        # POST Edición
        zona_creada = Zona.objects.get(nombre='Zona Sur Costera')
        resp_edit = self.client.post(reverse('gestion:zona_editar', args=[zona_creada.id]), {
            'nombre': 'Zona Sur Costera Modificada',
            'descripcion': 'Área ampliada',
            'dia_reparto_defecto': 'Miércoles y Sábados',
            'activa': True
        })
        self.assertRedirects(resp_edit, reverse('gestion:zonas_list'))
        zona_creada.refresh_from_db()
        self.assertEqual(zona_creada.nombre, 'Zona Sur Costera Modificada')

        # POST Toggle Estado
        self.client.post(reverse('gestion:zona_toggle', args=[zona_creada.id]))
        zona_creada.refresh_from_db()
        self.assertFalse(zona_creada.activa)

    # --------------------------------------------------------------------------
    # 4. Gestión de Vendedores y Asignación Histórica de Zonas
    # --------------------------------------------------------------------------

    def test_gestion_vendedores_y_asignacion_historica_zonas(self):
        """Alta y edición de vendedores con asignación y desasignación conservando histórico."""
        self.client.force_login(self.admin_user)

        # POST Alta Válida con dos zonas asignadas
        resp_crear = self.client.post(reverse('gestion:vendedor_crear'), {
            'legajo': 'VEND-002',
            'nombre': 'Laura',
            'apellido': 'Fernández',
            'dni': '32111222',
            'telefono': '341-9876543',
            'comision_porcentaje': '4.00',
            'activo': True,
            'zonas': [self.zona1.id, self.zona2.id]
        })
        self.assertRedirects(resp_crear, reverse('gestion:vendedores_list'))
        vendedor_nuevo = Vendedor.objects.get(legajo='VEND-002')
        self.assertEqual(vendedor_nuevo.asignaciones_zona.filter(activo=True).count(), 2)

        # POST Duplicado de Legajo
        resp_dup = self.client.post(reverse('gestion:vendedor_crear'), {
            'legajo': 'VEND-002',
            'nombre': 'Otro',
            'apellido': 'Pérez',
            'comision_porcentaje': '2.00',
            'activo': True,
        })
        self.assertEqual(resp_dup.status_code, 200)
        self.assertContains(resp_dup, 'Ya existe un vendedor con el legajo')

        # POST Edición: desasignar zona2 sin borrar registro (debe quedar activo=False)
        resp_edit = self.client.post(reverse('gestion:vendedor_editar', args=[vendedor_nuevo.id]), {
            'legajo': 'VEND-002',
            'nombre': 'Laura',
            'apellido': 'Fernández de Gómez',
            'dni': '32111222',
            'telefono': '341-9876543',
            'comision_porcentaje': '4.50',
            'activo': True,
            'zonas': [self.zona1.id]  # Solo zona 1 seleccionada
        })
        self.assertRedirects(resp_edit, reverse('gestion:vendedores_list'))

        # Verificación histórica: el registro de asignación a zona2 no se borró
        asig_zona2 = AsignacionZonaVendedor.objects.filter(vendedor=vendedor_nuevo, zona=self.zona2).first()
        self.assertIsNotNone(asig_zona2, "El registro de asignación no debe eliminarse")
        self.assertFalse(asig_zona2.activo, "La asignación desmarcada debe quedar inactiva")

        # Asignación a zona1 permanece activa
        asig_zona1 = AsignacionZonaVendedor.objects.filter(vendedor=vendedor_nuevo, zona=self.zona1).first()
        self.assertTrue(asig_zona1.activo)

    def test_vinculacion_usuario_vendedor_incompatible_rechazada(self):
        """
        Solo se pueden vincular cuentas de usuario con rol VENDEDOR que no pertenezcan a otro vendedor.
        Usuarios con rol CLIENTE, ADMIN o SUPERVISOR son rechazados.
        """
        self.client.force_login(self.admin_user)

        # 1. Intentar vincular cuenta de CLIENTE
        resp_cliente_link = self.client.post(reverse('gestion:vendedor_crear'), {
            'legajo': 'VEND-ERR-1',
            'nombre': 'Test',
            'apellido': 'Incompatible',
            'comision_porcentaje': '3.00',
            'activo': True,
            'usuario': self.cliente_user.id
        })
        self.assertEqual(resp_cliente_link.status_code, 200)
        self.assertContains(resp_cliente_link, "Solo se pueden vincular cuentas de usuario")
        self.assertFalse(Vendedor.objects.filter(legajo='VEND-ERR-1').exists())

        # 2. Intentar vincular cuenta de ADMIN
        resp_admin_link = self.client.post(reverse('gestion:vendedor_crear'), {
            'legajo': 'VEND-ERR-2',
            'nombre': 'Test',
            'apellido': 'Incompatible',
            'comision_porcentaje': '3.00',
            'activo': True,
            'usuario': self.admin_user.id
        })
        self.assertEqual(resp_admin_link.status_code, 200)
        self.assertContains(resp_admin_link, "Solo se pueden vincular cuentas de usuario")
        self.assertFalse(Vendedor.objects.filter(legajo='VEND-ERR-2').exists())

        # 3. Intentar vincular un usuario VENDEDOR que ya está asignado a otro vendedor
        self.vendedor.usuario = self.vendedor_user
        self.vendedor.save()

        resp_dup_vend = self.client.post(reverse('gestion:vendedor_crear'), {
            'legajo': 'VEND-ERR-3',
            'nombre': 'Test',
            'apellido': 'Duplicado',
            'comision_porcentaje': '3.00',
            'activo': True,
            'usuario': self.vendedor_user.id
        })
        self.assertEqual(resp_dup_vend.status_code, 200)
        self.assertContains(resp_dup_vend, "Solo se pueden vincular cuentas de usuario")
        self.assertFalse(Vendedor.objects.filter(legajo='VEND-ERR-3').exists())

        # 4. Vincular un usuario con rol VENDEDOR libre: permitido
        vend_libre = Usuario.objects.create_user(
            username='vendedor_libre',
            cuit_dni='20777777777',
            email='libre@vendedor.com',
            password='Password123!',
            rol='VENDEDOR'
        )
        resp_ok = self.client.post(reverse('gestion:vendedor_crear'), {
            'legajo': 'VEND-OK',
            'nombre': 'Vendedor',
            'apellido': 'Valido',
            'comision_porcentaje': '3.00',
            'activo': True,
            'usuario': vend_libre.id
        })
        self.assertRedirects(resp_ok, reverse('gestion:vendedores_list'))
        v = Vendedor.objects.get(legajo='VEND-OK')
        self.assertEqual(v.usuario, vend_libre)

    # --------------------------------------------------------------------------
    # 5. Gestión de Clientes (Con y Sin Usuario)
    # --------------------------------------------------------------------------

    def test_alta_cliente_sin_usuario(self):
        """Un cliente puede crearse sin cuenta de usuario portal de manera opcional."""
        self.client.force_login(self.supervisor_user)

        data = {
            'razon_social': 'Almacén Central SRL',
            'nombre_fantasia': 'El Central',
            'cuit': '30-99887766-5',
            'condicion_iva': self.condicion_iva.id,
            'domicilio': 'Av. Pellegrini 2500',
            'localidad': self.localidad.id,
            'zona': self.zona1.id,
            'vendedor': self.vendedor.id,
            'dia_reparto': 1,
            'tipo_lista_precio': self.tipo_lista.id,
            'telefono': '341-1112233',
            'email': 'central@almacen.com',
            'monto_minimo_pedido': '5000.00',
            'estado': 'ACTIVO',
            'crear_usuario_portal': False,
        }

        resp = self.client.post(reverse('gestion:cliente_crear'), data)
        self.assertRedirects(resp, reverse('gestion:clientes_list'))

        cliente = Cliente.objects.get(cuit='30998877665')
        self.assertIsNone(cliente.usuario, "El cliente debe crearse sin usuario si no se solicitó")
        self.assertEqual(cliente.zona, self.zona1)
        self.assertEqual(cliente.vendedor, self.vendedor)
        self.assertEqual(cliente.tipo_lista_precio, self.tipo_lista)

    def test_alta_cliente_con_usuario_seguro(self):
        """Al solicitar usuario, se crea cuenta sin asignar CUIT como contraseña por defecto."""
        self.client.force_login(self.admin_user)

        data = {
            'razon_social': 'Supermercado Sol S.A.',
            'nombre_fantasia': 'Sol',
            'cuit': '30-77665544-3',
            'condicion_iva': self.condicion_iva.id,
            'domicilio': 'Bv. Oroño 1234',
            'localidad': self.localidad.id,
            'zona': self.zona2.id,
            'vendedor': self.vendedor.id,
            'dia_reparto': 2,
            'tipo_lista_precio': self.tipo_lista.id,
            'telefono': '341-4443322',
            'email': 'contacto@supersol.com',
            'monto_minimo_pedido': '10000.00',
            'estado': 'ACTIVO',
            'crear_usuario_portal': True,
            'password_portal': 'ClaveSuperSegura99!',
        }

        resp = self.client.post(reverse('gestion:cliente_crear'), data)
        self.assertRedirects(resp, reverse('gestion:clientes_list'))

        cliente = Cliente.objects.get(cuit='30776655443')
        self.assertIsNotNone(cliente.usuario)
        self.assertTrue(cliente.usuario.check_password('ClaveSuperSegura99!'))
        # Verificar que el CUIT NO es la contraseña
        self.assertFalse(cliente.usuario.check_password('30776655443'))

    def test_alta_cliente_duplicado_cuit_rechazado(self):
        """No permite registrar clientes con CUIT duplicado."""
        self.client.force_login(self.supervisor_user)

        # Crear primer cliente
        Cliente.objects.create(
            cuit='30123456789',
            razon_social='Existente SRL',
            domicilio='Calle 1',
            condicion_iva=self.condicion_iva,
            tipo_lista_precio=self.tipo_lista
        )

        data = {
            'razon_social': 'Nuevo Intento SRL',
            'cuit': '30-12345678-9',  # Mismo CUIT con guiones
            'condicion_iva': self.condicion_iva.id,
            'domicilio': 'Calle 2',
            'tipo_lista_precio': self.tipo_lista.id,
            'estado': 'ACTIVO',
        }

        resp = self.client.post(reverse('gestion:cliente_crear'), data)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Ya existe un cliente registrado con este CUIT')

    def test_alta_cliente_colision_identificador_y_email_sin_registros_parciales(self):
        """
        Si al solicitar usuario de portal colisiona CUIT/username o email:
        - Muestra error visible en el formulario.
        - NO presenta como exitosa la habilitación del portal.
        - No crea registros parciales ni usuarios huérfanos.
        """
        self.client.force_login(self.supervisor_user)

        # 1. Creamos un usuario standalone existente (ej. un operador interno) sin Cliente
        Usuario.objects.create_user(
            username='20999888776',
            cuit_dni='20999888776',
            email='operador_existente@test.com',
            password='Password123!',
            rol='ADMIN'
        )

        # Intento de alta con CUIT que colisiona con el username/cuit_dni del usuario existente
        data_cuit_colision = {
            'razon_social': 'Cliente Colision CUIT SRL',
            'cuit': '20-99988877-6',
            'condicion_iva': self.condicion_iva.id,
            'domicilio': 'Calle 100',
            'localidad': self.localidad.id,
            'zona': self.zona1.id,
            'vendedor': self.vendedor.id,
            'dia_reparto': 1,
            'tipo_lista_precio': self.tipo_lista.id,
            'monto_minimo_pedido': '0.00',
            'crear_usuario_portal': True,
            'password_portal': 'PassValido123!',
            'estado': 'ACTIVO',
        }
        resp = self.client.post(reverse('gestion:cliente_crear'), data_cuit_colision)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Ya existe un usuario en el sistema con el identificador")
        self.assertFalse(Cliente.objects.filter(cuit='20999888776').exists())

        # 2. Colisión de Email
        data_email_colision = {
            'razon_social': 'Cliente Colision Email SRL',
            'cuit': '30-88888888-8',
            'email': 'operador_existente@test.com',  # Email del usuario existente
            'condicion_iva': self.condicion_iva.id,
            'domicilio': 'Calle 200',
            'localidad': self.localidad.id,
            'zona': self.zona1.id,
            'vendedor': self.vendedor.id,
            'dia_reparto': 1,
            'tipo_lista_precio': self.tipo_lista.id,
            'monto_minimo_pedido': '0.00',
            'crear_usuario_portal': True,
            'password_portal': 'PassValido123!',
            'estado': 'ACTIVO',
        }
        resp_email = self.client.post(reverse('gestion:cliente_crear'), data_email_colision)
        self.assertEqual(resp_email.status_code, 200)
        self.assertContains(resp_email, "ya se encuentra registrado por otro usuario")
        self.assertFalse(Cliente.objects.filter(cuit='30888888888').exists())
        self.assertFalse(Usuario.objects.filter(username='30888888888').exists())

    def test_alta_cliente_con_contrasena_autogenerada_comunica_clave(self):
        """Si no se ingresa contraseña, el sistema genera una temporal y la comunica claramente."""
        self.client.force_login(self.admin_user)
        data = {
            'razon_social': 'Farmacia Central SRL',
            'cuit': '30-33221100-9',
            'condicion_iva': self.condicion_iva.id,
            'domicilio': 'San Martin 500',
            'localidad': self.localidad.id,
            'zona': self.zona1.id,
            'vendedor': self.vendedor.id,
            'dia_reparto': 1,
            'tipo_lista_precio': self.tipo_lista.id,
            'monto_minimo_pedido': '0.00',
            'crear_usuario_portal': True,
            'password_portal': '',  # En blanco para autogenerar
            'estado': 'ACTIVO',
        }
        resp = self.client.post(reverse('gestion:cliente_crear'), data, follow=True)
        self.assertEqual(resp.status_code, 200)
        cliente = Cliente.objects.get(cuit='30332211009')
        self.assertIsNotNone(cliente.usuario)
        # El mensaje de feedback debe incluir la contraseña generada
        self.assertContains(resp, "Contraseña inicial generada:")

    # --------------------------------------------------------------------------
    # 6. Gestión de Productos y Preservación de Stock / Kardex
    # --------------------------------------------------------------------------

    def test_alta_producto_con_alicuota_valida_y_precios(self):
        """Alta de producto calculando precios para listas activas."""
        self.client.force_login(self.supervisor_user)

        data = {
            'codigo': 'PROD-100',
            'codigo_barras': '7791234567890',
            'nombre': 'Leche Entera 1L',
            'descripcion': 'Sachet 1 Litro Ultra Pasteurizada',
            'categoria': self.categoria.id,
            'marca': self.marca.id,
            'alicuota_iva': '21.00',
            'costo_base': '850.00',
            'punto_reposicion': '20',
            'controla_stock': True,
            'activo': True,
            f'recargo_lista_{self.tipo_lista.id}': '30.00',
            f'descuento_lista_{self.tipo_lista.id}': '0.00',
        }

        resp = self.client.post(reverse('gestion:producto_crear'), data)
        self.assertRedirects(resp, reverse('gestion:productos_list'))

        prod = Producto.objects.get(codigo='PROD-100')
        self.assertEqual(prod.costo_base, Decimal('850.00'))
        self.assertEqual(prod.stock_actual, 0)

        # Precio calculado en lista
        precio = PrecioProducto.objects.filter(producto=prod, tipo_lista=self.tipo_lista).first()
        self.assertIsNotNone(precio)
        self.assertGreater(precio.precio_final, Decimal('850.00'))

    def test_preservacion_estricta_de_stock_y_kardex_en_edicion(self):
        """
        Una edición comercial no debe modificar stock_actual saltándose el Kardex.
        """
        self.client.force_login(self.admin_user)

        # Crear producto con stock inicial establecido
        prod = Producto.objects.create(
            codigo='PROD-KARDEX',
            nombre='Yogur Firme Vainilla',
            categoria=self.categoria,
            marca=self.marca,
            costo_base=Decimal('500.00'),
            alicuota_iva=Decimal('21.00'),
            stock_actual=100,  # Stock existente
            controla_stock=True,
            activo=True
        )

        # Registrar un movimiento en Kardex
        MovimientoStock.objects.create(
            producto=prod,
            tipo_movimiento='ENTRADA_COMPRA',
            cantidad=100,
            stock_anterior=0,
            stock_resultante=100,
            documento_referencia='FAC-0001',
            usuario=self.admin_user
        )

        movimientos_antes = MovimientoStock.objects.filter(producto=prod).count()
        self.assertEqual(movimientos_antes, 1)

        # Intentar modificar stock_actual directamente mediante POST en la edición comercial
        data_edit = {
            'codigo': 'PROD-KARDEX',
            'nombre': 'Yogur Firme Vainilla Modificado',
            'categoria': self.categoria.id,
            'marca': self.marca.id,
            'alicuota_iva': '21.00',
            'costo_base': '550.00',
            'stock_actual': '999',  # Intento indebido de alterar stock
            'punto_reposicion': '10',
            'controla_stock': True,
            'activo': True,
        }

        resp = self.client.post(reverse('gestion:producto_editar', args=[prod.id]), data_edit)
        self.assertRedirects(resp, reverse('gestion:productos_list'))

        prod.refresh_from_db()
        # El costo y nombre cambian, pero el stock_actual permanece inalterado en 100
        self.assertEqual(prod.nombre, 'Yogur Firme Vainilla Modificado')
        self.assertEqual(prod.costo_base, Decimal('550.00'))
        self.assertEqual(prod.stock_actual, 100, "El stock_actual no debe ser alterado saltándose el Kardex")

        # El libro de Kardex no fue contaminado
        movimientos_despues = MovimientoStock.objects.filter(producto=prod).count()
        self.assertEqual(movimientos_despues, 1)

    def test_edicion_producto_preserva_stock_concurrente_e_ignora_post_stock(self):
        """
        Si un movimiento del Kardex cambia el stock en la base de datos mientras el formulario
        está abierto, la edición comercial NUNCA sobrescribe el stock con el valor anterior
        ni con un stock enviado maliciosamente por POST.
        """
        self.client.force_login(self.admin_user)

        prod = Producto.objects.create(
            codigo='PROD-CONCURRENTE',
            nombre='Aceite de Girasol 900ml',
            categoria=self.categoria,
            marca=self.marca,
            costo_base=Decimal('1200.00'),
            alicuota_iva=Decimal('21.00'),
            stock_actual=10,  # Stock inicial en DB
            controla_stock=True,
            activo=True
        )

        # Simulamos que ingresa un remito o movimiento en Kardex antes de guardar el form
        Producto.objects.filter(pk=prod.pk).update(stock_actual=45)

        # Se envía POST con cambios comerciales y con un intento de fijar stock en 999
        data_edit = {
            'codigo': 'PROD-CONCURRENTE',
            'nombre': 'Aceite de Girasol 900ml Especial',
            'categoria': self.categoria.id,
            'marca': self.marca.id,
            'alicuota_iva': '21.00',
            'costo_base': '1350.00',
            'stock_actual': '999',  # Debe ser totalmente ignorado
            'punto_reposicion': '15',
            'controla_stock': True,
            'activo': True,
        }

        resp = self.client.post(reverse('gestion:producto_editar', args=[prod.id]), data_edit)
        self.assertRedirects(resp, reverse('gestion:productos_list'))

        prod.refresh_from_db()
        self.assertEqual(prod.nombre, 'Aceite de Girasol 900ml Especial')
        self.assertEqual(prod.costo_base, Decimal('1350.00'))
        # El stock DEBE permanecer en 45 (el stock concurrente nuevo), NO en 10 ni en 999
        self.assertEqual(prod.stock_actual, 45)
