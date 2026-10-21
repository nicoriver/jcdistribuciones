from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from usuarios.models import Usuario
from clientes.models import Cliente, Vendedor, CondicionIVA
from productos.models import Categoria, AlicuotaIVA, Producto, ListaPrecio, PrecioProducto, Presentacion
from pedidos.models import Pedido, DetallePedido


class PortalTestCase(TestCase):
    def setUp(self):
        # 1. Crear Alicuota y Categoria
        self.alicuota = AlicuotaIVA.objects.create(descripcion='21%', porcentaje=Decimal('21.00'))
        self.categoria = Categoria.objects.create(nombre='Bebidas', activo=True)

        # 2. Crear Productos
        self.prod1 = Producto.objects.create(
            codigo='BEB01',
            nombre='Gaseosa Cola 2.25L',
            costo=Decimal('1000.00'),
            categoria=self.categoria,
            alicuota_iva=self.alicuota,
            activo=True
        )

        self.presentacion = Presentacion.objects.create(
            producto=self.prod1,
            nombre='Pack x6',
            factor_unidades=Decimal('6.00'),
            es_default=False
        )

        # 3. Lista de Precio
        self.lista_precio = ListaPrecio.objects.create(
            nombre='Mayorista General',
            activa=True
        )

        self.precio_prod1 = PrecioProducto.objects.create(
            lista=self.lista_precio,
            producto=self.prod1,
            precio_neto=Decimal('1000.00'),
            precio_final=Decimal('1210.00')
        )

        # 4. Usuarios y Perfiles
        # Usuario Vendedor 1
        self.user_vendedor1 = Usuario.objects.create_user(
            username='vendedor1',
            email='vendedor1@jcdistribuciones.com',
            password='password123',
            nombre_completo='Carlos Vendedor',
            rol='VENDEDOR'
        )
        self.vendedor1 = Vendedor.objects.create(
            usuario=self.user_vendedor1,
            nombre='Carlos Vendedor',
            comision_porcentaje=Decimal('2.50'),
            activo=True
        )

        # Usuario Vendedor 2 (Otro vendedor)
        self.user_vendedor2 = Usuario.objects.create_user(
            username='vendedor2',
            email='vendedor2@jcdistribuciones.com',
            password='password123',
            nombre_completo='Roberto Vendedor',
            rol='VENDEDOR'
        )
        self.vendedor2 = Vendedor.objects.create(
            usuario=self.user_vendedor2,
            nombre='Roberto Vendedor',
            activo=True
        )

        # Usuario Cliente 1
        self.user_cliente = Usuario.objects.create_user(
            username='cliente_cuit',
            email='cliente@supermercado.com',
            password='password123',
            cuit='30123456789',
            nombre_completo='Supermercado Central SRL',
            rol='CLIENTE'
        )
        self.condicion_iva = CondicionIVA.objects.create(
            codigo='RI',
            descripcion='Responsable Inscripto',
            discrimina_iva=True
        )

        self.cliente = Cliente.objects.create(
            usuario=self.user_cliente,
            razon_social='Supermercado Central SRL',
            cuit='30123456789',
            condicion_iva=self.condicion_iva,
            vendedor=self.vendedor1,
            lista_precio_default=self.lista_precio,
            monto_minimo_pedido=Decimal('2000.00'),
            estado='ACTIVO'
        )

        # Usuario Cliente 2 (Asignado a Vendedor 2)
        self.user_cliente2 = Usuario.objects.create_user(
            username='cliente2_cuit',
            email='cliente2@almacen.com',
            password='password123',
            cuit='30999999999',
            nombre_completo='Almacen Don Pedro',
            rol='CLIENTE'
        )

        self.cliente2 = Cliente.objects.create(
            usuario=self.user_cliente2,
            razon_social='Almacen Don Pedro',
            cuit='30999999999',
            condicion_iva=self.condicion_iva,
            vendedor=self.vendedor2,
            lista_precio_default=self.lista_precio,
            monto_minimo_pedido=Decimal('1000.00'),
            estado='ACTIVO'
        )

        self.client = Client()

    def test_login_view(self):
        # GET login
        response = self.client.get(reverse('portal:login'))
        self.assertEqual(response.status_code, 200)

        # POST login exitoso con CUIT
        response = self.client.post(reverse('portal:login'), {
            'identificador': '30-12345678-9',
            'password': 'password123'
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['user'].is_authenticated)

    def test_catalogo_y_agregar_carrito_api(self):
        # Autenticar cliente
        self.client.login(username='cliente_cuit', password='password123')

        # Ver catálogo
        response = self.client.get(reverse('portal:catalogo'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Gaseosa Cola 2.25L')

        # Agregar item vía API AJAX (POST JSON)
        api_url = reverse('portal:api_agregar_carrito')
        payload = {
            'producto_id': self.prod1.id,
            'presentacion_id': self.presentacion.id,
            'cantidad': 2
        }
        response = self.client.post(api_url, data=payload, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'ok')
        self.assertEqual(data['cart_count'], 1)

        # Verificar borrador en BD (2 unidades * $1000 = $2000 neto)
        pedido = Pedido.objects.get(cliente=self.cliente, estado='BORRADOR')
        self.assertEqual(pedido.items.count(), 1)
        self.assertEqual(pedido.monto_subtotal_neto, Decimal('2000.00'))

    def test_flujo_completo_pedido_y_revision_vendedor(self):
        # 1. Cliente se loguea y agrega item
        self.client.login(username='cliente_cuit', password='password123')
        
        self.client.post(reverse('portal:api_agregar_carrito'), data={
            'producto_id': self.prod1.id,
            'cantidad': 5
        }, content_type='application/json')

        # 2. Ver Carrito
        response = self.client.get(reverse('portal:carrito'))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['cumple_minimo'])

        # 3. Enviar Pedido
        response = self.client.post(reverse('portal:enviar_pedido'), {
            'observaciones_cliente': 'Por favor entregar por la mañana.'
        }, follow=True)
        self.assertEqual(response.status_code, 200)

        pedido = Pedido.objects.get(cliente=self.cliente)
        self.assertIn(pedido.estado, ['PENDIENTE_REVISION', 'ENVIADO'])
        self.assertEqual(pedido.observaciones_cliente, 'Por favor entregar por la mañana.')

        # 4. Mis Pedidos Cliente
        response = self.client.get(reverse('portal:mis_pedidos'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, pedido.numero_pedido)

        # Detalle de Pedido Cliente
        response = self.client.get(reverse('portal:detalle_pedido', kwargs={'pedido_id': pedido.id}))
        self.assertEqual(response.status_code, 200)

        # 5. Vendedor 2 (No asignado) intenta ver/gestionar pedido -> 403 Forbidden
        self.client.login(username='vendedor2', password='password123')
        response = self.client.get(reverse('portal:vendedor_gestionar_pedido', kwargs={'pedido_id': pedido.id}))
        self.assertEqual(response.status_code, 403)

        # 6. Vendedor 1 (Asignado) abre panel y aprueba pedido
        self.client.login(username='vendedor1', password='password123')
        response = self.client.get(reverse('portal:vendedor_pedidos'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, pedido.numero_pedido)

        # Aprobar pedido
        response = self.client.post(
            reverse('portal:vendedor_gestionar_pedido', kwargs={'pedido_id': pedido.id}),
            {'accion': 'aprobar'},
            follow=True
        )
        self.assertEqual(response.status_code, 200)

        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, 'APROBADO')
        self.assertIsNotNone(pedido.fecha_aprobacion)

    # --------------------------------------------------------------------------
    # PRUEBAS DE PRE-VENTA MÓVIL EN CALLE
    # --------------------------------------------------------------------------

    def test_vendedor_lista_solo_sus_clientes_en_seleccion(self):
        # Vendedor 1 se loguea
        self.client.login(username='vendedor1', password='password123')
        response = self.client.get(reverse('portal:vendedor_seleccionar_cliente'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Supermercado Central SRL')
        self.assertNotContains(response, 'Almacen Don Pedro')

    def test_vendedor_toma_pedido_preventa_completo(self):
        # Vendedor 1 se loguea y selecciona su cliente
        self.client.login(username='vendedor1', password='password123')

        url_tomar = reverse('portal:vendedor_tomar_pedido', kwargs={'cliente_id': self.cliente.id})
        response = self.client.get(url_tomar)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Supermercado Central SRL')

        # Agregar producto vía API de pre-venta
        api_url = reverse('portal:vendedor_agregar_item_api')
        payload = {
            'cliente_id': self.cliente.id,
            'producto_id': self.prod1.id,
            'presentacion_id': self.presentacion.id,
            'cantidad': 3
        }
        response = self.client.post(api_url, data=payload, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'ok')

        # Confirmar pre-venta
        pedido_borrador = Pedido.objects.get(cliente=self.cliente, estado='BORRADOR')
        confirm_url = reverse('portal:vendedor_confirmar_preventa', kwargs={'pedido_id': pedido_borrador.id})
        response = self.client.post(confirm_url, follow=True)
        self.assertEqual(response.status_code, 200)

        pedido_borrador.refresh_from_db()
        self.assertEqual(pedido_borrador.estado, 'APROBADO')
        self.assertEqual(pedido_borrador.aprobado_por, self.user_vendedor1)
        self.assertIsNotNone(pedido_borrador.fecha_aprobacion)

    def test_vendedor_bloqueado_de_tomar_pedido_a_cliente_ajeno(self):
        # Vendedor 1 intenta tomar pedido para Cliente 2 (asignado a Vendedor 2) -> 403 Forbidden
        self.client.login(username='vendedor1', password='password123')
        url_tomar_ajeno = reverse('portal:vendedor_tomar_pedido', kwargs={'cliente_id': self.cliente2.id})
        response = self.client.get(url_tomar_ajeno)
        self.assertEqual(response.status_code, 403)
