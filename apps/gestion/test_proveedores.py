"""
Pruebas de comportamiento para la gestión de proveedores y unificación visual (DIST-005).
Cubre:
- Operaciones CRUD de Proveedor en /gestion/.
- Validación de formato y unicidad de CUIT.
- Toggle de estado (activar / desactivar) exclusivo por POST (405 en GET).
- Control de acceso RBAC estricto (SUPERVISOR, ADMIN, superuser vs FACTURACION, VENDEDOR, CLIENTE).
- Visibilidad condicional de navegación en base_gestion.html.
- Unificación visual de barra superior, marca y menú de usuario.
"""

from decimal import Decimal
from django.test import TestCase, Client as HttpClient
from django.urls import reverse

from usuarios.models import Usuario
from proveedores.models import Proveedor
from productos.models import Producto, Categoria, Marca
from compras.models import Compra, DetalleCompra


class ProveedoresYVisualBehaviorTests(TestCase):
    """
    Suite de pruebas para DIST-005.
    """

    def setUp(self):
        super().setUp()
        self.client = HttpClient()

        # Usuarios con distintos roles
        self.admin_user = Usuario.objects.create_user(
            username='admin_dist005',
            cuit_dni='20111111111',
            email='admin@test.com',
            password='AdminPassword123!',
            nombre='Admin',
            apellido='Test',
            rol='ADMIN',
            is_staff=True
        )

        self.supervisor_user = Usuario.objects.create_user(
            username='supervisor_dist005',
            cuit_dni='20222222222',
            email='supervisor@test.com',
            password='SupervisorPassword123!',
            nombre='Supervisor',
            apellido='Test',
            rol='SUPERVISOR'
        )

        self.superuser = Usuario.objects.create_superuser(
            username='superuser_dist005',
            cuit_dni='20999999999',
            email='root@test.com',
            password='RootPassword123!'
        )

        self.facturacion_user = Usuario.objects.create_user(
            username='fabio_facturacion',
            cuit_dni='20444444444',
            email='fabio@test.com',
            password='FabioPassword123!',
            nombre='Fabio',
            apellido='Facturacion',
            rol='FACTURACION'
        )

        self.vendedor_user = Usuario.objects.create_user(
            username='vendedor_dist005',
            cuit_dni='20333333333',
            email='vendedor@test.com',
            password='VendedorPassword123!',
            nombre='Vendedor',
            apellido='Test',
            rol='VENDEDOR'
        )

        self.cliente_user = Usuario.objects.create_user(
            username='cliente_dist005',
            cuit_dni='20555555555',
            email='cliente@test.com',
            password='ClientePassword123!',
            nombre='Cliente',
            apellido='Test',
            rol='CLIENTE'
        )

        # Proveedor base para tests
        self.proveedor_base = Proveedor.objects.create(
            cuit='30111222334',
            razon_social='Distribuidora Molinos S.A.',
            domicilio='Av. Belgrano 500, Rosario',
            telefono='0341-4223344',
            email='contacto@molinos.com.ar',
            contacto_nombre='Carlos Gómez',
            activo=True
        )

    # --------------------------------------------------------------------------
    # 1. PERMISOS Y CONTROL DE ACCESO (RBAC)
    # --------------------------------------------------------------------------

    def test_acceso_proveedores_permitido_para_admin_y_supervisor_y_superuser(self):
        """ADMIN, SUPERVISOR y superusuario pueden acceder al listado de proveedores."""
        for user in [self.admin_user, self.supervisor_user, self.superuser]:
            self.client.force_login(user)
            resp = self.client.get(reverse('gestion:proveedores_list'))
            self.assertEqual(
                resp.status_code, 200,
                f"El usuario con rol {user.rol} (superuser={user.is_superuser}) debe tener acceso 200 OK."
            )
            self.assertContains(resp, 'Distribuidora Molinos S.A.')

    def test_acceso_proveedores_denegado_para_facturacion_vendedor_cliente(self):
        """FACTURACION, VENDEDOR y CLIENTE reciben HTTP 403 Forbidden en Proveedores."""
        for user in [self.facturacion_user, self.vendedor_user, self.cliente_user]:
            self.client.force_login(user)
            resp = self.client.get(reverse('gestion:proveedores_list'))
            self.assertEqual(
                resp.status_code, 403,
                f"El usuario con rol {user.rol} debe recibir 403 Forbidden en proveedores_list."
            )

            # También en alta
            resp_crear = self.client.get(reverse('gestion:proveedor_crear'))
            self.assertEqual(resp_crear.status_code, 403)

            # También en edición
            resp_edit = self.client.get(reverse('gestion:proveedor_editar', args=[self.proveedor_base.id]))
            self.assertEqual(resp_edit.status_code, 403)

            # También en toggle
            resp_toggle = self.client.post(reverse('gestion:proveedor_toggle', args=[self.proveedor_base.id]))
            self.assertEqual(resp_toggle.status_code, 403)

    # --------------------------------------------------------------------------
    # 2. CRUD DE PROVEEDORES
    # --------------------------------------------------------------------------

    def test_creacion_proveedor_exitoso(self):
        """Un supervisor puede dar de alta un nuevo proveedor con datos válidos."""
        self.client.force_login(self.supervisor_user)

        data = {
            'cuit': '30-99887766-5',  # Formato con guiones debe ser limpiado
            'razon_social': 'Lácteos La Serenísima S.A.',
            'domicilio': 'Ruta 5 Km 80, Gral. Rodríguez',
            'telefono': '011-4876-5432',
            'email': 'ventas@serenisima.com.ar',
            'contacto_nombre': 'Mariana Rossi',
            'activo': True,
        }

        resp = self.client.post(reverse('gestion:proveedor_crear'), data)
        self.assertRedirects(resp, reverse('gestion:proveedores_list'))

        prov = Proveedor.objects.get(razon_social='Lácteos La Serenísima S.A.')
        self.assertEqual(prov.cuit, '30998877665', "El CUIT debe guardarse limpio de guiones.")
        self.assertEqual(prov.contacto_nombre, 'Mariana Rossi')
        self.assertTrue(prov.activo)

    def test_creacion_proveedor_cuit_duplicado_rechazado(self):
        """No permite registrar un proveedor con un CUIT ya existente."""
        self.client.force_login(self.admin_user)

        data = {
            'cuit': '30-11122233-4',  # CUIT del proveedor base existente
            'razon_social': 'Molinos Clon S.A.',
            'activo': True,
        }

        resp = self.client.post(reverse('gestion:proveedor_crear'), data)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Ya existe un proveedor registrado con el CUIT')
        self.assertFalse(Proveedor.objects.filter(razon_social='Molinos Clon S.A.').exists())

    def test_creacion_proveedor_cuit_invalido_rechazado(self):
        """CUIT no numérico o con longitud inválida es rechazado."""
        self.client.force_login(self.supervisor_user)

        # CUIT muy corto
        resp1 = self.client.post(reverse('gestion:proveedor_crear'), {
            'cuit': '12345',
            'razon_social': 'Proveedor Corto',
            'activo': True,
        })
        self.assertEqual(resp1.status_code, 200)
        self.assertContains(resp1, 'El CUIT debe tener entre 10 y 11 dígitos numéricos')

        # CUIT con letras
        resp2 = self.client.post(reverse('gestion:proveedor_crear'), {
            'cuit': '30ABC456789',
            'razon_social': 'Proveedor Letras',
            'activo': True,
        })
        self.assertEqual(resp2.status_code, 200)
        self.assertContains(resp2, 'El CUIT debe contener únicamente números')

    def test_edicion_proveedor_exitoso(self):
        """Permite modificar los datos de un proveedor conservando su CUIT."""
        self.client.force_login(self.supervisor_user)

        data = {
            'cuit': self.proveedor_base.cuit,
            'razon_social': 'Distribuidora Molinos S.A. Modificada',
            'domicilio': 'Nueva Dirección 789',
            'telefono': '0341-9998888',
            'email': 'nuevo_contacto@molinos.com.ar',
            'contacto_nombre': 'Roberto Gómez',
            'activo': True,
        }

        resp = self.client.post(
            reverse('gestion:proveedor_editar', args=[self.proveedor_base.id]),
            data
        )
        self.assertRedirects(resp, reverse('gestion:proveedores_list'))

        self.proveedor_base.refresh_from_db()
        self.assertEqual(self.proveedor_base.razon_social, 'Distribuidora Molinos S.A. Modificada')
        self.assertEqual(self.proveedor_base.telefono, '0341-9998888')
        self.assertEqual(self.proveedor_base.contacto_nombre, 'Roberto Gómez')

    # --------------------------------------------------------------------------
    # 3. TOGGLE DE ESTADO (POST-ONLY / 405 EN GET)
    # --------------------------------------------------------------------------

    def test_toggle_proveedor_post_cambia_estado(self):
        """Un POST a proveedor_toggle invierte el estado de activo a inactivo y viceversa."""
        self.client.force_login(self.admin_user)
        self.assertTrue(self.proveedor_base.activo)

        # Desactivar
        resp1 = self.client.post(reverse('gestion:proveedor_toggle', args=[self.proveedor_base.id]))
        self.assertRedirects(resp1, reverse('gestion:proveedores_list'))
        self.proveedor_base.refresh_from_db()
        self.assertFalse(self.proveedor_base.activo)

        # Reactivar
        resp2 = self.client.post(reverse('gestion:proveedor_toggle', args=[self.proveedor_base.id]))
        self.assertRedirects(resp2, reverse('gestion:proveedores_list'))
        self.proveedor_base.refresh_from_db()
        self.assertTrue(self.proveedor_base.activo)

    def test_toggle_proveedor_get_retorna_405_method_not_allowed(self):
        """Un intento de GET a proveedor_toggle debe retornar estrictamente HTTP 405."""
        self.client.force_login(self.admin_user)
        resp = self.client.get(reverse('gestion:proveedor_toggle', args=[self.proveedor_base.id]))
        self.assertEqual(
            resp.status_code, 405,
            "El toggle de estado solo debe aceptar solicitudes POST y rechazar GET con 405."
        )

    # --------------------------------------------------------------------------
    # 4. PRESERVACIÓN DE RELACIONES CON COMPRAS Y PRODUCTOS
    # --------------------------------------------------------------------------

    def test_proveedor_preserva_relaciones_con_compras_y_productos(self):
        """Verifica que el listado cuente correctamente compras y productos asociados."""
        self.client.force_login(self.supervisor_user)

        # Crear categoría y marca mínimas
        cat = Categoria.objects.create(nombre='Harinas')
        marca = Marca.objects.create(nombre='Molinos')

        # Producto vinculado al proveedor
        prod = Producto.objects.create(
            codigo='HAR-001',
            nombre='Harina 000 1kg',
            categoria=cat,
            marca=marca,
            costo_base=Decimal('500.00'),
            alicuota_iva=Decimal('21.00'),
            proveedor_habitual=self.proveedor_base,
            activo=True
        )

        # Compra vinculada al proveedor
        compra = Compra.objects.create(
            proveedor=self.proveedor_base,
            usuario=self.admin_user,
            nro_comprobante_proveedor='FC-0001-00000001',
            total_compra=Decimal('15000.00')
        )

        resp = self.client.get(reverse('gestion:proveedores_list'))
        self.assertEqual(resp.status_code, 200)

        # Verificar contadores anotados en el contexto
        proveedores_context = list(resp.context['proveedores'])
        prov_en_context = next(p for p in proveedores_context if p.id == self.proveedor_base.id)
        self.assertEqual(prov_en_context.total_compras, 1)
        self.assertEqual(prov_en_context.total_productos, 1)

    # --------------------------------------------------------------------------
    # 5. UNIFICACIÓN VISUAL Y VISIBILIDAD CONDICIONAL DEL MENÚ
    # --------------------------------------------------------------------------

    def test_sidebar_visibilidad_para_supervisor_y_admin(self):
        """ADMIN y SUPERVISOR ven Proveedores, Vendedores y Zonas en el menú lateral."""
        for user in [self.admin_user, self.supervisor_user, self.superuser]:
            self.client.force_login(user)
            resp = self.client.get(reverse('gestion:dashboard'))
            self.assertEqual(resp.status_code, 200)
            self.assertContains(resp, reverse('gestion:proveedores_list'))
            self.assertContains(resp, reverse('gestion:vendedores_list'))
            self.assertContains(resp, reverse('gestion:zonas_list'))

    def test_sidebar_oculta_proveedores_vendedores_zonas_a_facturacion(self):
        """
        Un usuario con rol FACTURACION (como Fabio) NO debe ver en el menú lateral
        los enlaces a Proveedores, Vendedores ni Zonas (política RBAC pactada).
        """
        self.client.force_login(self.facturacion_user)
        resp = self.client.get(reverse('gestion:dashboard'))
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, reverse('gestion:proveedores_list'))
        self.assertNotContains(resp, reverse('gestion:vendedores_list'))
        self.assertNotContains(resp, reverse('gestion:zonas_list'))

    def test_topbar_visual_sin_supervisor_hardcodeado_y_con_dropdown(self):
        """
        La barra superior no tiene 'JC Distribuciones | Supervisor' hardcodeado,
        presenta 'JC Distribuciones' como marca y contiene el dropdown del usuario.
        """
        self.client.force_login(self.supervisor_user)
        resp = self.client.get(reverse('gestion:dashboard'))
        self.assertEqual(resp.status_code, 200)

        # No debe contener el título rígido anterior
        self.assertNotContains(resp, 'JC Distribuciones | Supervisor')
        # Debe contener la marca limpia
        self.assertContains(resp, 'JC Distribuciones')
        # Debe contener enlaces del dropdown de usuario
        self.assertContains(resp, reverse('portal:catalogo'))
        self.assertContains(resp, reverse('portal:logout'))
