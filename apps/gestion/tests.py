from decimal import Decimal
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

from geografia.models import Provincia, Localidad, Zona
from clientes.models import Vendedor, Cliente
from productos.models import Categoria, Marca, Producto, Presentacion, TipoListaPrecio
from productos.services import CalculadoraPreciosService
from pedidos.models import Pedido, DetallePedido
from pedidos.services import PedidoService
from comprobantes.models import Remito

Usuario = get_user_model()


class GestionSupervisorTests(TestCase):
    """
    Pruebas integrales de la Mesa de Control del Supervisor (/gestion/):
    - Ciclo completo web: Pedido creado -> Aprobado por Vendedor -> Facturado por Supervisor -> Redirección a impresión A4.
    - Emisión de Remito Directo de mostrador.
    - Seguridad RBAC: usuarios con rol CLIENTE o VENDEDOR reciben HTTP 403 Forbidden en /gestion/ y al intentar facturar.
    """

    def setUp(self):
        # 1. Usuarios con roles diferenciados
        self.user_supervisor = Usuario.objects.create_user(
            username='supervisor_mesa',
            cuit_dni='20320000015',
            password='Password123!',
            nombre='Laura',
            apellido='Supervisora',
            rol='SUPERVISOR'
        )
        self.user_vendedor = Usuario.objects.create_user(
            username='vendedor_calle',
            cuit_dni='20320000023',
            password='Password123!',
            nombre='Diego',
            apellido='Preventista',
            rol='VENDEDOR'
        )
        self.user_cliente = Usuario.objects.create_user(
            username='cliente_portal',
            cuit_dni='30715544332',
            password='Password123!',
            nombre='Comercio',
            apellido='Minorista',
            rol='CLIENTE'
        )

        # 2. Geografía, Vendedor, Lista y Cliente
        self.provincia = Provincia.objects.create(nombre='Entre Ríos')
        self.localidad = Localidad.objects.create(
            provincia=self.provincia,
            nombre='Concordia',
            codigo_postal='3200'
        )
        self.zona = Zona.objects.create(
            nombre='Zona Centro Comercial',
            dia_reparto_defecto='Lunes y Jueves',
            activa=True
        )
        self.vendedor = Vendedor.objects.create(
            usuario=self.user_vendedor,
            nombre='Diego',
            apellido='Preventista',
            legajo='VEND-701',
            comision_porcentaje=Decimal('5.00'),
            activo=True
        )

        self.lista_precio = TipoListaPrecio.objects.create(
            nombre='Lista General Comercio',
            descripcion='Lista general para comercios',
            activa=True
        )

        self.cliente = Cliente.objects.create(
            usuario=self.user_cliente,
            cuit='30715544332',
            razon_social='Despensa Don José SRL',
            nombre_fantasia='Don José',
            domicilio='Urquiza 1240',
            localidad=self.localidad,
            zona=self.zona,
            vendedor=self.vendedor,
            tipo_lista_precio=self.lista_precio,
            activo=True
        )

        # 3. Producto con stock y presentación
        self.categoria = Categoria.objects.create(nombre='Bebidas', activa=True)
        self.marca = Marca.objects.create(nombre='Manaos', activa=True)
        self.producto = Producto.objects.create(
            codigo='BEB-225',
            nombre='Gaseosa Cola 2.25L',
            categoria=self.categoria,
            marca=self.marca,
            costo_base=Decimal('1000.00'),
            alicuota_iva=Decimal('21.00'),
            controla_stock=True,
            stock_actual=60,
            punto_reposicion=18,
            activo=True
        )
        self.presentacion_pack = Presentacion.objects.create(
            producto=self.producto,
            nombre='Pack x 6 Botellas',
            factor_conversion=6,
            codigo_barras='7791234560006'
        )
        CalculadoraPreciosService.actualizar_precios_producto(self.producto)

    def test_ciclo_completo_pedido_aprobado_facturado_por_supervisor_y_redireccion_a4(self):
        """
        a) Prueba el ciclo completo:
           Pedido creado -> Aprobado por Vendedor -> Facturado por Supervisor desde /gestion/ ->
           Redirección inmediata a /comprobantes/remito/<id>/imprimir/ (vista de impresión A4).
        b) Verifica descuento de stock y estado FACTURADO_REMITO sin doble facturación.
        """
        # 1. Crear pedido en BORRADOR
        pedido = Pedido.objects.create(
            cliente=self.cliente,
            vendedor=self.vendedor,
            lista_precio=self.lista_precio,
            estado='BORRADOR',
            observaciones='Pedido de preventa semanal'
        )
        DetallePedido.objects.create(
            pedido=pedido,
            producto=self.producto,
            presentacion=self.presentacion_pack,
            factor_unidades=6,
            cantidad=2,
            precio_unitario=Decimal('9000.00'),
            porcentaje_descuento=Decimal('5.00')
        )
        pedido.recalcular_totales()

        # 2. Enviar a revisión y aprobar por Vendedor
        PedidoService.enviar_a_revision(pedido)
        PedidoService.aprobar_pedido(pedido, usuario=self.user_vendedor)
        self.assertEqual(pedido.estado, 'APROBADO')

        # 3. Supervisor ingresa a la Bandeja de Facturación y ve el pedido aprobado
        self.client.force_login(self.user_supervisor)
        resp_bandeja = self.client.get(reverse('gestion:bandeja_facturacion'))
        self.assertEqual(resp_bandeja.status_code, 200)
        self.assertContains(resp_bandeja, pedido.numero_pedido)

        # 4. Supervisor presiona "Facturar y Emitir Remito" (POST)
        url_facturar = reverse('gestion:facturar_pedido', kwargs={'pedido_id': pedido.id})
        resp_facturar = self.client.post(url_facturar)

        # Verificar que se creó el Remito y que redirige a la vista de impresión A4
        remito = Remito.objects.first()
        self.assertIsNotNone(remito)
        expected_print_url = reverse('comprobantes:imprimir_remito', kwargs={'remito_id': remito.id})
        self.assertRedirects(resp_facturar, expected_print_url)

        # 5. Verificar estado del pedido y descuento de stock (60 - 2*6 = 48)
        pedido.refresh_from_db()
        self.producto.refresh_from_db()
        self.assertEqual(pedido.estado, 'FACTURADO_REMITO')
        self.assertEqual(pedido.remito_asociado_id, remito.id)
        self.assertEqual(self.producto.stock_actual, 48)

        # 6. Verificar que intentar volver a facturar por POST es rechazado (HTTP 400) y no duplica remito
        resp_doble = self.client.post(url_facturar)
        self.assertEqual(resp_doble.status_code, 400)
        self.assertEqual(Remito.objects.count(), 1)
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.stock_actual, 48)

    def test_seguridad_rbac_cliente_y_vendedor_reciben_403_forbidden(self):
        """
        c) Verifica seguridad estricta:
           Un usuario con rol CLIENTE o VENDEDOR que intente acceder a /gestion/,
           /gestion/facturacion/, /gestion/remito-directo/ o facturar un pedido
           debe recibir HTTP 403 Forbidden.
        """
        pedido = Pedido.objects.create(
            cliente=self.cliente,
            vendedor=self.vendedor,
            lista_precio=self.lista_precio,
            estado='APROBADO'
        )
        DetallePedido.objects.create(
            pedido=pedido,
            producto=self.producto,
            factor_unidades=1,
            cantidad=5,
            precio_unitario=Decimal('1500.00')
        )

        urls_protegidas_get = [
            reverse('gestion:dashboard'),
            reverse('gestion:bandeja_facturacion'),
            reverse('gestion:remito_directo'),
        ]
        url_facturar_post = reverse('gestion:facturar_pedido', kwargs={'pedido_id': pedido.id})

        # Probar con usuario CLIENTE
        self.client.force_login(self.user_cliente)
        for url in urls_protegidas_get:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 403, f"CLIENTE debería recibir 403 en {url}")

        resp_post_cliente = self.client.post(url_facturar_post)
        self.assertEqual(resp_post_cliente.status_code, 403)

        # Probar con usuario VENDEDOR
        self.client.force_login(self.user_vendedor)
        for url in urls_protegidas_get:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 403, f"VENDEDOR debería recibir 403 en {url}")

        resp_post_vendedor = self.client.post(url_facturar_post)
        self.assertEqual(resp_post_vendedor.status_code, 403)

        # Confirmar que el pedido sigue sin facturarse
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, 'APROBADO')
        self.assertEqual(Remito.objects.count(), 0)

    def test_venta_directa_remito_mostrador_supervisor(self):
        """
        Verifica que el Supervisor pueda emitir un Remito directo desde /gestion/remito-directo/
        sin pedido previo, descontando stock y redirigiendo a la impresión A4.
        """
        self.client.force_login(self.user_supervisor)
        url_directo = reverse('gestion:remito_directo')

        resp = self.client.post(url_directo, {
            'cliente_id': self.cliente.id,
            'vendedor_id': self.vendedor.id,
            'observaciones': 'Venta directa mostrador efectivo',
            'producto_id[]': [str(self.producto.id)],
            'presentacion_id[]': [''],
            'cantidad[]': ['10'],
            'precio_unitario[]': ['1500.00'],
            'porcentaje_descuento[]': ['0.00'],
        })

        remito = Remito.objects.first()
        self.assertIsNotNone(remito)
        self.assertRedirects(resp, reverse('comprobantes:imprimir_remito', kwargs={'remito_id': remito.id}))

        self.producto.refresh_from_db()
        self.assertEqual(self.producto.stock_actual, 50)
        self.assertEqual(remito.total_comercial, Decimal('15000.00'))


class AuditoriaIntegralEstresTestCase(TestCase):
    """
    Suite de Auditoría Integral y Prueba de Estrés (Puntos 3, 4 y 5):
    - Matriz RBAC completa (Supervisor con permisos operativos, aislamiento por vendedor).
    - Reglas financieras: Caso testigo $3.811,50, inspección de DecimalField(14,2) y estrés de grandes montos.
    - Circuito punta a punta: Pedido -> Aprobado -> Remito A4 -> Kardex SALIDA_REMITO -> Inmutabilidad -> NC/NCF.
    """

    def test_auditoria_rbac_supervisor_permisos_y_aislamiento_cartera(self):
        from django.core.management import call_command
        call_command('setup_roles')

        sup = Usuario.objects.create_user(
            username='sup_audit',
            cuit_dni='20399990011',
            password='Password123!',
            rol='SUPERVISOR'
        )
        # Verificar permisos efectivos de Supervisor sobre todas las entidades operativas
        permisos_clave = [
            'clientes.add_cliente', 'clientes.change_cliente',
            'clientes.add_vendedor', 'clientes.change_vendedor',
            'geografia.add_zona', 'geografia.change_zona',
            'proveedores.add_proveedor', 'proveedores.change_proveedor',
            'productos.add_producto', 'productos.change_producto',
            'compras.add_compra', 'compras.view_compra',
            'pedidos.change_pedido', 'pedidos.view_pedido',
            'comprobantes.add_remito', 'comprobantes.view_remito',
        ]
        for perm in permisos_clave:
            self.assertTrue(sup.has_perm(perm), f"El rol SUPERVISOR debe poseer el permiso {perm}")

        # Verificar aislamiento de cartera por vendedor
        u_v1 = Usuario.objects.create_user(username='v1_audit', cuit_dni='20399990022', password='123', rol='VENDEDOR')
        u_v2 = Usuario.objects.create_user(username='v2_audit', cuit_dni='20399990033', password='123', rol='VENDEDOR')
        v1 = Vendedor.objects.create(usuario=u_v1, legajo='VA-1', nombre='V1', apellido='A')
        v2 = Vendedor.objects.create(usuario=u_v2, legajo='VA-2', nombre='V2', apellido='B')
        z = Zona.objects.create(nombre='Zona Audit', dia_reparto_defecto='Lunes')
        lista = TipoListaPrecio.objects.create(nombre='Lista Audit')

        c1 = Cliente.objects.create(cuit='30799990011', razon_social='Cliente V1', domicilio='Dir 1', zona=z, vendedor=v1, tipo_lista_precio=lista)
        c2 = Cliente.objects.create(cuit='30799990022', razon_social='Cliente V2', domicilio='Dir 2', zona=z, vendedor=v2, tipo_lista_precio=lista)

        qs_v1 = Cliente.objects.para_usuario(u_v1)
        self.assertIn(c1, qs_v1)
        self.assertNotIn(c2, qs_v1)

    def test_auditoria_precision_decimal_14_2_y_caso_testigo_canonico(self):
        from productos.models import PrecioProducto
        from compras.models import Compra, DetalleCompra
        from comprobantes.models import DetalleRemito, NotaCreditoInterna

        # 1. Caso testigo: Costo $2.500,00 | Recargo 40% | IVA 21% | Descuento 10% -> Neto $3.500,00 | Final $3.811,50
        p_final = CalculadoraPreciosService.calcular_precio_final(
            costo=Decimal('2500.00'),
            recargo_porc=Decimal('40.00'),
            iva_porc=Decimal('21.00'),
            descuento_porc=Decimal('10.00')
        )
        self.assertEqual(p_final, Decimal('3811.50'))

        # 2. Verificar que todos los campos monetarios tengan max_digits=14, decimal_places=2
        campos_monetarios = [
            (Producto, 'costo_base'),
            (PrecioProducto, 'precio_neto'),
            (PrecioProducto, 'precio_final'),
            (Compra, 'total_compra'),
            (DetalleCompra, 'precio_costo_unitario'),
            (DetalleCompra, 'subtotal'),
            (Pedido, 'total_estimado'),
            (DetallePedido, 'precio_unitario'),
            (DetallePedido, 'subtotal'),
            (Remito, 'subtotal_bruto'),
            (Remito, 'total_descuento'),
            (Remito, 'monto_total'),
            (DetalleRemito, 'precio_unitario_historico'),
            (DetalleRemito, 'subtotal'),
            (NotaCreditoInterna, 'monto_total'),
        ]
        for modelo, campo_nombre in campos_monetarios:
            field = modelo._meta.get_field(campo_nombre)
            self.assertEqual(field.max_digits, 14, f"{modelo.__name__}.{campo_nombre} debe tener max_digits=14")
            self.assertEqual(field.decimal_places, 2, f"{modelo.__name__}.{campo_nombre} debe tener decimal_places=2")

    def test_estres_circuito_remito_kardex_inmutabilidad_y_topes_nc(self):
        from django.core.exceptions import ValidationError
        from productos.models import PrecioProducto
        from comprobantes.services import RemitoService
        from stock.models import MovimientoStock

        sup = Usuario.objects.create_user(username='sup_estres', cuit_dni='20388880011', password='123', rol='SUPERVISOR')
        u_vend = Usuario.objects.create_user(username='vend_estres', cuit_dni='20388880022', password='123', rol='VENDEDOR')
        vend = Vendedor.objects.create(usuario=u_vend, legajo='VE-01', nombre='Pedro', apellido='Ventas')
        zona = Zona.objects.create(nombre='Zona Estrés', dia_reparto_defecto='Miércoles')
        lista = TipoListaPrecio.objects.create(nombre='Lista Estrés Mayorista')
        cliente = Cliente.objects.create(
            cuit='30788880011',
            razon_social='Distribuidora Mayorista del Litoral SA',
            domicilio='Ruta 14 Km 250',
            zona=zona,
            vendedor=vend,
            tipo_lista_precio=lista,
            activo=True
        )
        cat = Categoria.objects.create(nombre='Aceites Mayoristas', activa=True)
        prod = Producto.objects.create(
            codigo='ACE-5000',
            nombre='Bidón Aceite Girasol 5L',
            categoria=cat,
            costo_base=Decimal('2500.00'),
            alicuota_iva=Decimal('21.00'),
            controla_stock=True,
            stock_actual=500,
            punto_reposicion=50,
            activo=True
        )
        pres_caja = Presentacion.objects.create(producto=prod, nombre='Caja x 4 Bidones', factor_conversion=4)
        precio_prod = PrecioProducto.objects.create(
            producto=prod,
            tipo_lista=lista,
            porcentaje_recargo=Decimal('40.00'),
            porcentaje_descuento=Decimal('10.00')
        )
        # Neto = 3500.00 | Final unitario = 3811.50 | Caja x4 = 15246.00
        self.assertEqual(precio_prod.precio_neto, Decimal('3500.00'))
        self.assertEqual(precio_prod.precio_final, Decimal('3811.50'))

        # 1. Crear Pedido -> Aprobar -> Facturar a Remito (10 Cajas x 4 = 40 unidades base)
        pedido = Pedido.objects.create(cliente=cliente, vendedor=vend, lista_precio=lista, estado='BORRADOR')
        DetallePedido.objects.create(
            pedido=pedido,
            producto=prod,
            presentacion=pres_caja,
            factor_unidades=4,
            cantidad=10,
            precio_unitario=Decimal('15246.00'),
            porcentaje_descuento=Decimal('0.00')
        )
        pedido.recalcular_totales()
        PedidoService.enviar_a_revision(pedido)
        PedidoService.aprobar_pedido(pedido, usuario=u_vend)

        # Stock sigue en 500 antes de emitir Remito
        prod.refresh_from_db()
        self.assertEqual(prod.stock_actual, 500)

        remito = PedidoService.facturar_pedido_a_remito(pedido=pedido, supervisor=sup)
        prod.refresh_from_db()
        self.assertEqual(prod.stock_actual, 460)  # 500 - 40

        mov = MovimientoStock.objects.filter(producto=prod, tipo_movimiento='SALIDA_REMITO').first()
        self.assertIsNotNone(mov)
        self.assertEqual(mov.stock_anterior, 500)
        self.assertEqual(mov.stock_resultante, 460)
        self.assertEqual(mov.cantidad, -40)

        # 2. Inmutabilidad histórica: sube el costo a $5.000,00 y se recalculan listas
        prod.costo_base = Decimal('5000.00')
        prod.save()
        CalculadoraPreciosService.actualizar_precios_producto(prod)
        det_remito = remito.detalles.first()
        det_remito.refresh_from_db()
        self.assertEqual(det_remito.precio_unitario_historico, Decimal('15246.00'))
        self.assertEqual(remito.monto_total, Decimal('152460.00'))

        # 3. Notas de Crédito (NC y NCF) y tope de devolución
        with self.assertRaises(ValidationError):
            RemitoService.registrar_nota_credito(
                remito=remito,
                items_data=[{'detalle_remito_id': det_remito.id, 'cantidad': 11}],
                motivo_tipo='NC',
                usuario=sup
            )

        # Devolución física parcial de 2 cajas (8 unidades base) -> reingresa stock a 468
        RemitoService.registrar_nota_credito(
            remito=remito,
            items_data=[{'detalle_remito_id': det_remito.id, 'cantidad': 2}],
            motivo_tipo='NC',
            usuario=sup
        )
        prod.refresh_from_db()
        self.assertEqual(prod.stock_actual, 468)

