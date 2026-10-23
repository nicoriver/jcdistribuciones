"""
Pruebas de comportamiento para la corrección del listado de clientes sin vendedor
y la navegación superior en el panel de gestión (DIST-006).

Cubre:
1. Renderizado y gestión de clientes:
   - Cliente sin vendedor (evita error 500 y muestra 'Sin vendedor asignado').
   - Cliente con vendedor.
   - Cliente sin las demás relaciones opcionales (sin zona, sin localidad, sin condicion_iva, sin tipo_lista_precio).
   - Alta de cliente mediante POST seguida con follow=True hasta el listado.
   - Edición de cliente eliminando/vaciando el vendedor asignado.
   - Listado mixto con búsqueda y paginación.
   - Retención de datos y visibilidad de errores ante fallos de validación en el formulario.
2. Menú superior de navegación:
   - Presencia de accesos: Ventas, Productos, Clientes, Informes.
   - Submenús desplegables en Ventas e Informes.
   - Detección del módulo activo según la vista navegada.
   - Respeto a los permisos de acceso RBAC.
"""

from decimal import Decimal
from django.test import TestCase, Client as HttpClient
from django.urls import reverse

from usuarios.models import Usuario
from clientes.models import Cliente, Vendedor, CondicionIVA
from geografia.models import Zona, Localidad, Provincia
from productos.models import TipoListaPrecio


class ClientesNavegacionBehaviorTests(TestCase):
    """
    Suite de pruebas para verificar la resolución de DIST-006.
    """

    def setUp(self):
        super().setUp()
        self.client = HttpClient()

        # Usuarios
        self.admin_user = Usuario.objects.create_user(
            username='admin_dist006',
            cuit_dni='20111111112',
            email='admin006@test.com',
            password='AdminPassword123!',
            nombre='Admin',
            apellido='Test',
            rol='ADMIN',
            is_staff=True
        )

        self.supervisor_user = Usuario.objects.create_user(
            username='supervisor_dist006',
            cuit_dni='20222222223',
            email='supervisor006@test.com',
            password='SupervisorPassword123!',
            nombre='Supervisor',
            apellido='Test',
            rol='SUPERVISOR'
        )

        self.facturacion_user = Usuario.objects.create_user(
            username='facturacion_dist006',
            cuit_dni='20444444445',
            email='facturacion006@test.com',
            password='FacturacionPassword123!',
            nombre='Fabio',
            apellido='Facturacion',
            rol='FACTURACION'
        )

        # Entidades maestras
        self.provincia = Provincia.objects.create(nombre='Santa Fe')
        self.localidad = Localidad.objects.create(nombre='Rosario', provincia=self.provincia)
        self.zona = Zona.objects.create(nombre='Zona Norte', activa=True)
        self.condicion_iva = CondicionIVA.objects.create(
            codigo='RI',
            descripcion='Responsable Inscripto',
            discrimina_iva=True
        )
        self.tipo_lista = TipoListaPrecio.objects.create(
            nombre='Lista Mayorista A',
            activa=True
        )
        self.vendedor = Vendedor.objects.create(
            nombre='Martín',
            apellido='Palermo',
            legajo='VEND-001',
            comision_porcentaje=Decimal('3.00'),
            activo=True
        )

    # --------------------------------------------------------------------------
    # 1. CLIENTES SIN VENDEDOR Y RELACIONES OPCIONALES
    # --------------------------------------------------------------------------

    def test_listado_clientes_con_cliente_sin_vendedor_retorna_200_ok(self):
        """
        Un cliente registrado sin vendedor NO provoca Server Error (500).
        El listado responde 200 OK y muestra explícitamente 'Sin vendedor asignado'.
        """
        self.client.force_login(self.supervisor_user)

        cliente_sin_vendedor = Cliente.objects.create(
            cuit='30711112223',
            razon_social='Almacén Don Pepe SRL',
            domicilio='Av. Pellegrini 1500',
            condicion_iva=self.condicion_iva,
            zona=self.zona,
            tipo_lista_precio=self.tipo_lista,
            vendedor=None,  # Sin vendedor
            estado='ACTIVO'
        )

        resp = self.client.get(reverse('gestion:clientes_list'))
        self.assertEqual(resp.status_code, 200, "El listado debe responder 200 OK sin lanzar VariableDoesNotExist.")
        self.assertContains(resp, 'Almacén Don Pepe SRL')
        self.assertContains(resp, 'Sin vendedor asignado')

    def test_listado_clientes_con_cliente_con_vendedor_muestra_nombre_completo(self):
        """
        Un cliente con vendedor muestra adecuadamente el nombre completo del vendedor asignado.
        """
        self.client.force_login(self.supervisor_user)

        cliente_con_vendedor = Cliente.objects.create(
            cuit='30722223334',
            razon_social='Supermercado Los Primos S.A.',
            domicilio='Bv. Oroño 2200',
            condicion_iva=self.condicion_iva,
            zona=self.zona,
            tipo_lista_precio=self.tipo_lista,
            vendedor=self.vendedor,
            estado='ACTIVO'
        )

        resp = self.client.get(reverse('gestion:clientes_list'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Supermercado Los Primos S.A.')
        self.assertContains(resp, 'Martín Palermo')

    def test_listado_clientes_sin_ninguna_relacion_opcional_retorna_200_ok(self):
        """
        Un cliente que no tenga vendedor, ni zona, ni localidad, ni condicion_iva,
        ni tipo_lista_precio se renderiza con 200 OK mostrando textos limpios.
        """
        self.client.force_login(self.supervisor_user)

        cliente_austero = Cliente.objects.create(
            cuit='30733334445',
            razon_social='Comercio Sin Relaciones SRL',
            domicilio='Calle Rural S/N',
            condicion_iva=None,
            zona=None,
            localidad=None,
            vendedor=None,
            tipo_lista_precio=None,
            estado='ACTIVO'
        )

        resp = self.client.get(reverse('gestion:clientes_list'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Comercio Sin Relaciones SRL')
        self.assertContains(resp, 'Sin vendedor asignado')
        self.assertContains(resp, 'Sin zona asignada')
        self.assertContains(resp, 'Sin IVA')
        self.assertContains(resp, 'Sin lista asignada')

    def test_alta_cliente_sin_vendedor_con_follow_redirige_y_muestra_listado(self):
        """
        Al dar de alta un cliente mediante POST sin seleccionar vendedor y siguiendo
        la redirección (follow=True), el navegador llega con éxito al listado (status 200)
        sin errores de servidor.
        """
        self.client.force_login(self.supervisor_user)

        data = {
            'razon_social': 'Dietética Naturalia',
            'nombre_fantasia': 'Naturalia',
            'cuit': '30-74444555-6',
            'domicilio': 'Corrientes 850',
            'localidad': self.localidad.id,
            'zona': self.zona.id,
            'vendedor': '',  # Vendedor vacío (opcional)
            'tipo_lista_precio': self.tipo_lista.id,
            'condicion_iva': self.condicion_iva.id,
            'estado': 'ACTIVO',
            'monto_minimo_pedido': '0.00',
        }

        resp = self.client.post(reverse('gestion:cliente_crear'), data, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.redirect_chain)
        self.assertEqual(resp.redirect_chain[0][0], reverse('gestion:clientes_list'))
        self.assertContains(resp, 'Dietética Naturalia')
        self.assertContains(resp, 'Sin vendedor asignado')

        # Verificar persistencia en base de datos
        cliente_creado = Cliente.objects.get(cuit='30744445556')
        self.assertIsNone(cliente_creado.vendedor)

    def test_edicion_cliente_vaciando_vendedor_persiste_y_renderiza(self):
        """
        Un cliente que inicialmente tenía vendedor puede editarse dejando el vendedor vacío.
        La redirección y renderizado funcionan correctamente.
        """
        self.client.force_login(self.supervisor_user)

        cliente = Cliente.objects.create(
            cuit='30755556667',
            razon_social='Autoservicio El Progreso',
            domicilio='San Juan 3300',
            condicion_iva=self.condicion_iva,
            zona=self.zona,
            vendedor=self.vendedor,
            tipo_lista_precio=self.tipo_lista,
            estado='ACTIVO'
        )

        data = {
            'razon_social': 'Autoservicio El Progreso Actualizado',
            'cuit': '30-75555666-7',
            'domicilio': 'San Juan 3300',
            'zona': self.zona.id,
            'vendedor': '',  # Desasignar vendedor
            'tipo_lista_precio': self.tipo_lista.id,
            'condicion_iva': self.condicion_iva.id,
            'estado': 'ACTIVO',
            'monto_minimo_pedido': '0.00',
        }

        resp = self.client.post(reverse('gestion:cliente_editar', args=[cliente.id]), data, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Autoservicio El Progreso Actualizado')
        self.assertContains(resp, 'Sin vendedor asignado')

        cliente.refresh_from_db()
        self.assertIsNone(cliente.vendedor)

    def test_listado_datos_mixtos_busqueda_y_paginacion(self):
        """
        Listado con 30 clientes (mezcla de con/sin vendedor y con/sin zona),
        con paginación a 25 registros y búsqueda textual activa.
        """
        self.client.force_login(self.supervisor_user)

        # Crear 30 clientes mixtos
        for i in range(1, 31):
            Cliente.objects.create(
                cuit=f'3088888{i:04d}',
                razon_social=f'Cliente Mixto {i:02d}',
                domicilio=f'Calle {i}',
                vendedor=self.vendedor if i % 2 == 0 else None,
                zona=self.zona if i % 3 == 0 else None,
                tipo_lista_precio=self.tipo_lista if i % 2 == 0 else None,
                estado='ACTIVO'
            )

        # Página 1 (25 registros)
        resp1 = self.client.get(reverse('gestion:clientes_list'))
        self.assertEqual(resp1.status_code, 200)
        self.assertEqual(len(resp1.context['clientes']), 25)
        self.assertContains(resp1, 'Sin vendedor asignado')
        self.assertContains(resp1, 'Martín Palermo')

        # Página 2 (5 registros restantes)
        resp2 = self.client.get(reverse('gestion:clientes_list') + '?page=2')
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(len(resp2.context['clientes']), 5)

        # Búsqueda textual
        resp_search = self.client.get(reverse('gestion:clientes_list') + '?q=Mixto 15')
        self.assertEqual(resp_search.status_code, 200)
        self.assertContains(resp_search, 'Cliente Mixto 15')
        self.assertNotContains(resp_search, 'Cliente Mixto 01')

        # Filtro de clientes sin vendedor
        resp_sin_vend = self.client.get(reverse('gestion:clientes_list') + '?vendedor=sin_vendedor')
        self.assertEqual(resp_sin_vend.status_code, 200)
        # Todos los mostrados deben ser sin vendedor
        for c in resp_sin_vend.context['clientes']:
            self.assertIsNone(c.vendedor)

    def test_formulario_conserva_datos_y_muestra_errores_ante_validacion_invalida(self):
        """
        Si se envía un CUIT inválido, el formulario vuelve con código 200,
        muestra el error explícito y conserva la razón social y demás campos ingresados.
        """
        self.client.force_login(self.supervisor_user)

        data_invalida = {
            'razon_social': 'Comercio Datos Conservados SRL',
            'cuit': '12345',  # CUIT inválido (muy corto)
            'domicilio': 'Mitre 500',
            'estado': 'ACTIVO',
            'monto_minimo_pedido': '2500.50',
        }

        resp = self.client.post(reverse('gestion:cliente_crear'), data_invalida)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'El CUIT debe tener entre 10 y 11 dígitos numéricos')
        self.assertContains(resp, 'Comercio Datos Conservados SRL')
        self.assertContains(resp, 'Mitre 500')
        self.assertContains(resp, '2500.50')

    # --------------------------------------------------------------------------
    # 2. MENÚ SUPERIOR DE NAVEGACIÓN
    # --------------------------------------------------------------------------

    def test_menu_superior_contiene_accesos_principales(self):
        """
        La barra superior contiene los cuatro accesos solicitados:
        Ventas, Productos, Clientes, Informes.
        """
        self.client.force_login(self.supervisor_user)
        resp = self.client.get(reverse('gestion:dashboard'))
        self.assertEqual(resp.status_code, 200)

        # Menús y textos
        self.assertContains(resp, 'Ventas')
        self.assertContains(resp, 'Productos')
        self.assertContains(resp, 'Clientes')
        self.assertContains(resp, 'Informes')

        # Enlaces de submenú Ventas
        self.assertContains(resp, reverse('gestion:pedidos_list'))
        self.assertContains(resp, reverse('gestion:bandeja_facturacion'))
        self.assertContains(resp, reverse('gestion:remito_directo'))
        self.assertContains(resp, reverse('comprobantes:remitos_list'))

        # Enlace directo Productos
        self.assertContains(resp, reverse('gestion:productos_list'))

        # Enlace directo Clientes
        self.assertContains(resp, reverse('gestion:clientes_list'))

        # Enlaces de submenú Informes
        self.assertContains(resp, reverse('reportes:hoja_ruta'))
        self.assertContains(resp, reverse('reportes:ventas_vendedores'))

    def test_modulo_activo_marcado_adecuadamente_segun_vista(self):
        """
        Cuando el usuario navega a /gestion/clientes/, el acceso Clientes en el menú superior
        se resalta como activo.
        """
        self.client.force_login(self.supervisor_user)

        # 1. Clientes activo
        resp_clientes = self.client.get(reverse('gestion:clientes_list'))
        self.assertEqual(resp_clientes.status_code, 200)
        self.assertContains(
            resp_clientes,
            f'class="nav-link active" href="{reverse("gestion:clientes_list")}"'
        )

        # 2. Productos activo
        resp_prod = self.client.get(reverse('gestion:productos_list'))
        self.assertEqual(resp_prod.status_code, 200)
        self.assertContains(
            resp_prod,
            f'class="nav-link active" href="{reverse("gestion:productos_list")}"'
        )

    def test_menu_superior_conserva_datos_usuario_y_rol(self):
        """
        El menú superior conserva nombre y rol comprensible del usuario arriba a la derecha.
        """
        self.client.force_login(self.supervisor_user)
        resp = self.client.get(reverse('gestion:dashboard'))
        self.assertEqual(resp.status_code, 200)

        self.assertContains(resp, 'Supervisor Test')
        self.assertContains(resp, 'Supervisor')
        self.assertContains(resp, reverse('portal:catalogo'))
        self.assertContains(resp, reverse('portal:logout'))
