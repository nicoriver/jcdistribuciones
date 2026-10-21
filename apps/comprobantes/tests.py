from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.core.exceptions import ValidationError
from usuarios.models import Usuario
from geografia.models import Provincia, Localidad, Zona
from clientes.models import Vendedor, Cliente
from productos.models import Categoria, Marca, Producto, Presentacion, TipoListaPrecio, PrecioProducto
from productos.services import CalculadoraPreciosService
from stock.models import MovimientoStock
from comprobantes.models import PuntoVentaNumerador, Remito, DetalleRemito, NotaCreditoInterna
from comprobantes.services import RemitoService


class Modulo5RemitoTransaccionalTestCase(TestCase):
    def setUp(self):
        # 1. Usuarios: Supervisor y Vendedor
        self.supervisor = Usuario.objects.create_user(
            username='supervisor_facturacion',
            cuit_dni='20304050607',
            email='supervisor@jcdistribuciones.com',
            password='Password123!',
            rol='SUPERVISOR',
            is_staff=True
        )
        self.user_vendedor = Usuario.objects.create_user(
            username='vendedor_zona1',
            cuit_dni='20334455667',
            email='vendedor1@jcdistribuciones.com',
            password='Password123!',
            rol='VENDEDOR'
        )

        # 2. Geografía, Vendedor y Cliente
        self.provincia = Provincia.objects.create(nombre='Entre Ríos')
        self.zona = Zona.objects.create(
            nombre='Zona Paraná Centro',
            descripcion='Reparto comercial centro',
            dia_reparto_defecto='Lunes y Jueves',
            activa=True
        )
        self.localidad = Localidad.objects.create(
            nombre='Paraná',
            codigo_postal='3100',
            provincia=self.provincia
        )
        self.vendedor = Vendedor.objects.create(
            usuario=self.user_vendedor,
            legajo='VEND-001',
            nombre='Carlos',
            apellido='Gómez',
            comision_porcentaje=Decimal('5.00'),
            activo=True
        )

        # 3. Catálogo y Listas de Precios
        self.lista_mayorista = TipoListaPrecio.objects.create(
            nombre='Mayorista',
            descripcion='Lista Mayorista General',
            activa=True
        )
        self.cliente = Cliente.objects.create(
            cuit='30711223349',
            razon_social='Autoservicio El Sol SRL',
            nombre_fantasia='El Sol',
            domicilio='Av. Ramírez 1450',
            zona=self.zona,
            localidad=self.localidad,
            vendedor=self.vendedor,
            tipo_lista_precio=self.lista_mayorista,
            activo=True
        )

        self.categoria = Categoria.objects.create(nombre='Bebidas', activa=True)
        self.marca = Marca.objects.create(nombre='Quilmes', activa=True)

        # Producto con stock inicial = 100 unidades base
        self.producto = Producto.objects.create(
            codigo='BEB-100',
            nombre='Gaseosa Cola 2.25L',
            categoria=self.categoria,
            marca=self.marca,
            alicuota_iva=Decimal('21.00'),
            costo_base=Decimal('2500.00'),
            stock_actual=100,
            punto_reposicion=20,
            controla_stock=True,
            activo=True
        )

        # Presentación Pack x6 (factor_conversion = 6)
        self.presentacion_pack6 = Presentacion.objects.create(
            producto=self.producto,
            nombre='Pack x6',
            factor_conversion=6,
            es_default=True
        )

        # Precio en Lista Mayorista: Costo 2500, Recargo 40%, IVA 21%, Desc 10% -> Final unitario = 3811.50
        self.precio_prod = PrecioProducto.objects.create(
            producto=self.producto,
            tipo_lista=self.lista_mayorista,
            porcentaje_recargo=Decimal('40.00'),
            porcentaje_descuento=Decimal('10.00')
        )
        self.precio_prod.calcular_y_guardar(save=True)

    def test_a_emision_remito_numeracion_correlativa_segura(self):
        """
        a) Verifica la emisión de remito con numeración correlativa segura (R-0001-00000001, R-0001-00000002)
        bloqueando PuntoVentaNumerador sin saltos.
        """
        items = [
            {
                'producto': self.producto,
                'presentacion': self.presentacion_pack6,
                'factor_unidades': 6,
                'cantidad': 2,
                'precio_unitario_historico': Decimal('20000.00'),
                'porcentaje_descuento': Decimal('5.00'),
            }
        ]

        remito1 = RemitoService.emitir_remito(
            cliente=self.cliente,
            vendedor=self.vendedor,
            supervisor=self.supervisor,
            items=items,
            punto_venta=1,
            observaciones='Primer despacho'
        )
        self.assertEqual(remito1.punto_venta, 1)
        self.assertEqual(remito1.numero, 1)
        self.assertEqual(remito1.numero_completo, 'R-0001-00000001')
        # Bruto: 2 * 20000 = 40000.00 | Desc 5%: 2000.00 | Total: 38000.00
        self.assertEqual(remito1.subtotal_bruto, Decimal('40000.00'))
        self.assertEqual(remito1.total_descuento, Decimal('2000.00'))
        self.assertEqual(remito1.monto_total, Decimal('38000.00'))

        # Segundo remito consecutivo
        remito2 = RemitoService.emitir_remito(
            cliente=self.cliente,
            vendedor=self.vendedor,
            supervisor=self.supervisor,
            items=items,
            punto_venta=1
        )
        self.assertEqual(remito2.numero, 2)
        self.assertEqual(remito2.numero_completo, 'R-0001-00000002')

        numerador = PuntoVentaNumerador.objects.get(punto_venta=1, tipo_documento='REMITO')
        self.assertEqual(numerador.ultimo_numero, 2)

    def test_b_inmutabilidad_snapshot_precios_historicos(self):
        """
        b) Inmutabilidad: comprueba que si cambia el precio del catálogo al día siguiente,
        el DetalleRemito ya emitido conserva el valor histórico pactado.
        """
        precio_pactado = Decimal('3811.50')
        remito = RemitoService.emitir_remito(
            cliente=self.cliente,
            vendedor=self.vendedor,
            supervisor=self.supervisor,
            items=[
                {
                    'producto': self.producto,
                    'factor_unidades': 1,
                    'cantidad': 10,
                    'precio_unitario_historico': precio_pactado,
                    'porcentaje_descuento': Decimal('0.00'),
                }
            ]
        )

        detalle = remito.detalles.first()
        self.assertEqual(detalle.precio_unitario_historico, Decimal('3811.50'))
        self.assertEqual(detalle.subtotal, Decimal('38115.00'))

        # Al día siguiente aumenta el costo base un 100% y se actualiza todo el catálogo
        self.producto.costo_base = Decimal('5000.00')
        self.producto.nombre = 'Gaseosa Cola 2.25L Nueva Fórmula'
        self.producto.save()
        CalculadoraPreciosService.actualizar_precios_producto(self.producto)

        self.precio_prod.refresh_from_db()
        self.assertEqual(self.precio_prod.precio_final, Decimal('7623.00'))

        # El remito emitido con anterioridad permanece 100% inmutable
        detalle.refresh_from_db()
        remito.refresh_from_db()
        self.assertEqual(detalle.descripcion_historica, 'Gaseosa Cola 2.25L')
        self.assertEqual(detalle.precio_unitario_historico, Decimal('3811.50'))
        self.assertEqual(detalle.subtotal, Decimal('38115.00'))
        self.assertEqual(remito.monto_total, Decimal('38115.00'))

    def test_c_descuento_stock_unidades_base_y_kardex(self):
        """
        c) Verifica el descuento exacto de stock físico en unidades base (cantidad * factor_unidades)
        y su impacto en MovimientoStock con tipo 'SALIDA_REMITO'.
        """
        # Stock inicial: 100 unidades. Emitimos 3 Packs x6 -> 18 unidades base.
        remito = RemitoService.emitir_remito(
            cliente=self.cliente,
            vendedor=self.vendedor,
            supervisor=self.supervisor,
            items=[
                {
                    'producto': self.producto,
                    'presentacion': self.presentacion_pack6,
                    'factor_unidades': 6,
                    'cantidad': 3,
                    'precio_unitario_historico': Decimal('22869.00'),
                    'porcentaje_descuento': Decimal('0.00'),
                }
            ]
        )

        self.producto.refresh_from_db()
        self.assertEqual(self.producto.stock_actual, 82)  # 100 - (3 * 6) = 82

        mov = MovimientoStock.objects.filter(
            producto=self.producto,
            documento_referencia=remito.numero_completo
        ).first()
        self.assertIsNotNone(mov)
        self.assertEqual(mov.tipo_movimiento, 'SALIDA_REMITO')
        self.assertEqual(mov.cantidad, -18)
        self.assertEqual(mov.stock_anterior, 100)
        self.assertEqual(mov.stock_resultante, 82)
        self.assertEqual(mov.usuario, self.supervisor)

    def test_d_renderizado_impresion_remito_a4_http_200(self):
        """
        d) Verifica que la vista RemitoImpresionView responda HTTP 200 y renderice
        el formato A4 con los datos del remito, cliente, ítems y sin desglose visual de IVA.
        """
        remito = RemitoService.emitir_remito(
            cliente=self.cliente,
            vendedor=self.vendedor,
            supervisor=self.supervisor,
            items=[
                {
                    'producto': self.producto,
                    'presentacion': self.presentacion_pack6,
                    'factor_unidades': 6,
                    'cantidad': 2,
                    'precio_unitario_historico': Decimal('22869.00'),
                    'porcentaje_descuento': Decimal('10.00'),
                }
            ]
        )

        client = Client()
        client.force_login(self.supervisor)

        url = reverse('comprobantes:imprimir_remito', kwargs={'remito_id': remito.id})
        response = client.get(url)

        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        self.assertIn('JC DISTRIBUCIONES', content)
        self.assertIn(remito.numero_completo, content)
        self.assertIn(self.cliente.razon_social, content)
        self.assertIn('Gaseosa Cola 2.25L', content)
        self.assertIn('window.print()', content)

    def test_e_validacion_topes_devoluciones_nota_credito_nc_y_ncf(self):
        """
        e) Verifica la emisión de Notas de Crédito internas:
        - NCF (faltante) sin reingreso a stock.
        - NC (devolución) con reingreso a stock.
        - Bloqueo con ValidationError si se intenta devolver más unidades que las remitidas.
        """
        # Emitimos remito por 5 Packs x6 (30 unidades base). Stock pasa de 100 a 70.
        remito = RemitoService.emitir_remito(
            cliente=self.cliente,
            vendedor=self.vendedor,
            supervisor=self.supervisor,
            items=[
                {
                    'producto': self.producto,
                    'presentacion': self.presentacion_pack6,
                    'factor_unidades': 6,
                    'cantidad': 5,
                    'precio_unitario_historico': Decimal('20000.00'),
                    'porcentaje_descuento': Decimal('0.00'),
                }
            ]
        )
        detalle = remito.detalles.first()
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.stock_actual, 70)

        # 1. Registrar Faltante NCF por 1 Pack (sin retorno a stock)
        ncf = RemitoService.registrar_nota_credito(
            remito=remito,
            items_data=[{'detalle_remito_id': detalle.id, 'cantidad': 1}],
            motivo_tipo='NCF',
            usuario=self.supervisor,
            observaciones='Faltante detectado en descarga'
        )
        self.assertEqual(ncf.numero_nc, 'NCF-0001-00000001')
        self.assertFalse(ncf.reingresa_stock)
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.stock_actual, 70)  # NCF no mueve stock

        # 2. Registrar Devolución NC por 2 Packs con reingreso a stock (+12 unidades base -> stock 82)
        nc = RemitoService.registrar_nota_credito(
            remito=remito,
            items_data=[{'detalle_remito_id': detalle.id, 'cantidad': 2}],
            motivo_tipo='NC',
            reingresa_stock=True,
            usuario=self.supervisor,
            observaciones='Devolución comercial'
        )
        self.assertEqual(nc.numero_nc, 'NC-0001-00000001')
        self.assertTrue(nc.reingresa_stock)
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.stock_actual, 82)  # 70 + (2 * 6) = 82

        # Saldo devolvible restante: 5 remitidos - 1 NCF - 2 NC = 2 packs.
        # 3. Intentar devolver 3 Packs (excede el saldo disponible de 2) -> Debe fallar con ValidationError
        with self.assertRaises(ValidationError):
            RemitoService.registrar_nota_credito(
                remito=remito,
                items_data=[{'detalle_remito_id': detalle.id, 'cantidad': 3}],
                motivo_tipo='NC',
                reingresa_stock=True,
                usuario=self.supervisor
            )

        # Verificar que tras el error el stock sigue en 82 y cantidad_devuelta sigue en 3
        self.producto.refresh_from_db()
        detalle.refresh_from_db()
        self.assertEqual(self.producto.stock_actual, 82)
        self.assertEqual(detalle.cantidad_devuelta, 3)
        self.assertEqual(detalle.saldo_devolvible, 2)
