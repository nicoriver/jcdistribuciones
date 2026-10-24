"""
Pruebas para DIST-007: Descuento del distribuidor y carga de remitos por teclado.
Verifica:
1. Persistencia y límites del descuento del distribuidor en modelo y formulario.
2. Edición comercial de producto preservando stock y protegiendo Kardex concurrente.
3. Fecha comercial del remito, trazabilidad con fecha_emision y compatibilidad histórica.
4. Vendedor obtenido estrictamente del cliente y rechazo de manipulación en POST.
5. Cliente sin vendedor con mensaje controlado y enlace autorizado (sin error 500).
6. Lista Minorista predeterminada y selección de otra lista activa sin tocar ficha del cliente.
7. Validaciones ante precio ausente, código inexistente y rechazo de cantidades fraccionarias.
8. Caso testigo de cálculo de totales y coincidencia con comprobante guardado e impresión.
9. Preservación intacta de datos ingresados ante errores de validación.
10. Integridad de correlativo numerado, Kardex de stock y remitos originados desde pedidos.
"""

from decimal import Decimal
from datetime import date
from django.test import TestCase, Client as HttpClient
from django.urls import reverse
from django.core.exceptions import ValidationError

from usuarios.models import Usuario
from clientes.models import Cliente, Vendedor, CondicionIVA
from geografia.models import Zona, Localidad, Provincia
from productos.models import (
    Producto, Categoria, Marca, TipoListaPrecio, PrecioProducto, Presentacion
)
from stock.models import MovimientoStock
from comprobantes.models import PuntoVentaNumerador, Remito, DetalleRemito
from comprobantes.services import RemitoService
from pedidos.models import Pedido, DetallePedido
from pedidos.services import PedidoService
from gestion.forms import ProductoForm


class RemitoTecladoDescuentoDistribuidorTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.client = HttpClient()

        # 1. Usuarios
        self.supervisor = Usuario.objects.create_user(
            username='supervisor_dist007',
            cuit_dni='20999999991',
            email='supervisor007@test.com',
            password='Password123!',
            rol='SUPERVISOR',
            is_staff=True
        )
        self.vendedor_user1 = Usuario.objects.create_user(
            username='vendedor_user1',
            cuit_dni='20999999992',
            email='vend1@test.com',
            password='Password123!',
            rol='VENDEDOR'
        )
        self.vendedor_user2 = Usuario.objects.create_user(
            username='vendedor_user2',
            cuit_dni='20999999993',
            email='vend2@test.com',
            password='Password123!',
            rol='VENDEDOR'
        )

        # 2. Geografía y Vendedores
        self.provincia = Provincia.objects.create(nombre='Entre Ríos')
        self.localidad = Localidad.objects.create(nombre='Paraná', codigo_postal='3100', provincia=self.provincia)
        self.zona = Zona.objects.create(nombre='Zona 1', activa=True)

        self.vendedor_a = Vendedor.objects.create(
            usuario=self.vendedor_user1,
            legajo='V-001',
            nombre='Juan',
            apellido='Pérez',
            activo=True
        )
        self.vendedor_b = Vendedor.objects.create(
            usuario=self.vendedor_user2,
            legajo='V-002',
            nombre='Roberto',
            apellido='Gómez',
            activo=True
        )

        # 3. Listas de precios
        self.lista_minorista = TipoListaPrecio.objects.create(
            nombre='Minorista',
            descripcion='Lista de mostrador / minorista',
            activa=True
        )
        self.lista_mayorista = TipoListaPrecio.objects.create(
            nombre='Mayorista',
            descripcion='Lista para comercios mayoristas',
            activa=True
        )

        # 4. Clientes
        self.cliente_con_vendedor = Cliente.objects.create(
            cuit='30111111118',
            razon_social='Comercio Central SRL',
            nombre_fantasia='Central',
            domicilio='Calle Falsa 123',
            zona=self.zona,
            localidad=self.localidad,
            vendedor=self.vendedor_a,
            tipo_lista_precio=self.lista_mayorista,
            activo=True
        )
        self.cliente_sin_vendedor = Cliente.objects.create(
            cuit='30222222226',
            razon_social='Almacén Sin Vendedor',
            nombre_fantasia='Sin Vendedor',
            domicilio='Calle Vacía 456',
            zona=self.zona,
            localidad=self.localidad,
            vendedor=None,
            tipo_lista_precio=self.lista_minorista,
            activo=True
        )

        # 5. Catálogo de Productos
        self.categoria = Categoria.objects.create(nombre='Bebidas', activa=True)
        self.marca = Marca.objects.create(nombre='Marca X', activa=True)

        self.prod_1 = Producto.objects.create(
            codigo='00100',
            nombre='Gaseosa Cola 1.5L',
            categoria=self.categoria,
            marca=self.marca,
            alicuota_iva=Decimal('0.00'),
            costo_base=Decimal('1000.00'),
            descuento_distribuidor=Decimal('5.00'),
            stock_actual=100,
            controla_stock=True,
            activo=True
        )
        self.pres_base_1 = Presentacion.objects.create(
            producto=self.prod_1,
            nombre='Unidad Base',
            factor_conversion=1,
            es_default=True
        )

        self.prod_2 = Producto.objects.create(
            codigo='00200',
            nombre='Agua Mineral 2L',
            categoria=self.categoria,
            marca=self.marca,
            alicuota_iva=Decimal('0.00'),
            costo_base=Decimal('2000.00'),
            descuento_distribuidor=Decimal('0.00'),
            stock_actual=150,
            controla_stock=True,
            activo=True
        )
        self.pres_base_2 = Presentacion.objects.create(
            producto=self.prod_2,
            nombre='Unidad',
            factor_conversion=1,
            es_default=True
        )
        self.pres_pack_2 = Presentacion.objects.create(
            producto=self.prod_2,
            nombre='Pack x6',
            factor_conversion=6,
            es_default=False
        )

        # Precios en Lista Minorista (Caso Testigo):
        # prod_1: precio final unitario = 1000.00
        # prod_2: precio final unitario = 2000.00
        self.precio_prod1_minorista = PrecioProducto.objects.create(
            producto=self.prod_1,
            tipo_lista=self.lista_minorista,
            precio_neto=Decimal('1000.00'),
            precio_final=Decimal('1000.00')
        )
        self.precio_prod2_minorista = PrecioProducto.objects.create(
            producto=self.prod_2,
            tipo_lista=self.lista_minorista,
            precio_neto=Decimal('2000.00'),
            precio_final=Decimal('2000.00')
        )

        # Precios en Lista Mayorista
        self.precio_prod1_mayorista = PrecioProducto.objects.create(
            producto=self.prod_1,
            tipo_lista=self.lista_mayorista,
            precio_neto=Decimal('700.00'),
            precio_final=Decimal('847.00')
        )
        # Forzar valores exactos de precio_final
        PrecioProducto.objects.filter(id=self.precio_prod1_minorista.id).update(precio_final=Decimal('1000.00'))
        PrecioProducto.objects.filter(id=self.precio_prod2_minorista.id).update(precio_final=Decimal('2000.00'))
        PrecioProducto.objects.filter(id=self.precio_prod1_mayorista.id).update(precio_final=Decimal('847.00'), precio_neto=Decimal('700.00'))
        # prod_2 NO tiene precio en Lista Mayorista intencionalmente para pruebas

    # --------------------------------------------------------------------------
    # 1. Descuento del Distribuidor: persistencia y límites
    # --------------------------------------------------------------------------
    def test_descuento_distribuidor_persistencia_y_limites(self):
        # Valor por defecto es cero
        prod_def = Producto.objects.create(
            codigo='DEF-001',
            nombre='Producto Defecto',
            categoria=self.categoria
        )
        self.assertEqual(prod_def.descuento_distribuidor, Decimal('0.00'))

        # Acepta valores decimales entre 0 y 100
        prod_def.descuento_distribuidor = Decimal('15.50')
        prod_def.clean()
        prod_def.save()
        prod_def.refresh_from_db()
        self.assertEqual(prod_def.descuento_distribuidor, Decimal('15.50'))

        # Límite 100%
        prod_def.descuento_distribuidor = Decimal('100.00')
        prod_def.clean()
        prod_def.save()

        # Menor a 0 lanza ValidationError
        prod_def.descuento_distribuidor = Decimal('-0.01')
        with self.assertRaises(ValidationError):
            prod_def.clean()

        # Mayor a 100 lanza ValidationError
        prod_def.descuento_distribuidor = Decimal('100.01')
        with self.assertRaises(ValidationError):
            prod_def.clean()

        # Validación en formulario
        form_valid = ProductoForm(data={
            'codigo': 'FORM-01',
            'nombre': 'Producto Form Valido',
            'categoria': self.categoria.id,
            'alicuota_iva': '21.00',
            'costo_base': '500.00',
            'descuento_distribuidor': '25.50',
            'punto_reposicion': 5,
            'controla_stock': True,
            'activo': True
        })
        self.assertTrue(form_valid.is_valid(), form_valid.errors)
        self.assertEqual(form_valid.cleaned_data['descuento_distribuidor'], Decimal('25.50'))

        # Formulario con valor mayor a 100
        form_invalid = ProductoForm(data={
            'codigo': 'FORM-02',
            'nombre': 'Producto Form Invalido',
            'categoria': self.categoria.id,
            'alicuota_iva': '21.00',
            'costo_base': '500.00',
            'descuento_distribuidor': '105.00',
            'punto_reposicion': 5,
            'controla_stock': True,
            'activo': True
        })
        self.assertFalse(form_invalid.is_valid())
        self.assertIn('descuento_distribuidor', form_invalid.errors)

    # --------------------------------------------------------------------------
    # 2. Edición comercial sin alterar stock
    # --------------------------------------------------------------------------
    def test_edicion_comercial_producto_sin_alterar_stock(self):
        self.assertEqual(self.prod_1.stock_actual, 100)

        # Simular edición comercial cambiando costo y descuento del distribuidor
        form = ProductoForm(
            instance=self.prod_1,
            data={
                'codigo': self.prod_1.codigo,
                'nombre': 'Gaseosa Cola 1.5L Editada',
                'categoria': self.categoria.id,
                'alicuota_iva': '21.00',
                'costo_base': '950.00',
                'descuento_distribuidor': '12.00',
                'punto_reposicion': 10,
                'controla_stock': True,
                'activo': True
            }
        )
        self.assertTrue(form.is_valid(), form.errors)

        # Mientras el formulario estuvo abierto, ocurrió una venta concurrente que bajó el stock a 80
        Producto.objects.filter(pk=self.prod_1.pk).update(stock_actual=80)

        # Guardar el formulario de edición comercial
        producto_guardado = form.save()
        self.prod_1.refresh_from_db()

        # El stock_actual debe haberse preservado intacto en 80 (nunca pisado)
        self.assertEqual(self.prod_1.stock_actual, 80)
        self.assertEqual(self.prod_1.costo_base, Decimal('950.00'))
        self.assertEqual(self.prod_1.descuento_distribuidor, Decimal('12.00'))

    # --------------------------------------------------------------------------
    # 3. Fecha comercial y timestamp de creación
    # --------------------------------------------------------------------------
    def test_fecha_comercial_y_timestamp_creacion(self):
        fecha_elegida = date(2026, 11, 20)
        remito = RemitoService.emitir_remito(
            cliente=self.cliente_con_vendedor,
            supervisor=self.supervisor,
            items=[{
                'producto': self.prod_1,
                'cantidad': 1,
                'porcentaje_descuento': Decimal('0.00')
            }],
            fecha=fecha_elegida,
            tipo_lista_precio=self.lista_minorista
        )
        remito.refresh_from_db()
        self.assertEqual(remito.fecha, fecha_elegida)
        self.assertEqual(remito.fecha_comercial, fecha_elegida)
        # La fecha y hora de auditoría se mantiene separada y no sobreescrita
        self.assertIsNotNone(remito.fecha_emision)
        self.assertEqual(remito.fecha_emision.date(), date.today())

        # Compatibilidad retroactiva: remito histórico con fecha=None
        remito.fecha = None
        remito.save(update_fields=['fecha'])
        remito.refresh_from_db()
        self.assertIsNone(remito.fecha)
        self.assertEqual(remito.fecha_comercial, remito.fecha_emision.date())

    # --------------------------------------------------------------------------
    # 4. Vendedor obtenido del cliente y rechazo de manipulación en POST
    # --------------------------------------------------------------------------
    def test_vendedor_obtenido_del_cliente_y_rechazo_manipulacion(self):
        self.client.force_login(self.supervisor)
        url = reverse('gestion:remito_directo')

        # Intentar manipular enviando vendedor_id del vendedor B, cuando el cliente tiene asignado al vendedor A
        post_data = {
            'cliente_id': self.cliente_con_vendedor.id,
            'vendedor_id': self.vendedor_b.id,  # Manipulación en POST
            'tipo_lista_precio_id': self.lista_minorista.id,
            'fecha': '2026-10-24',
            'observaciones': 'Prueba manipulación',
            'codigo[]': ['00100'],
            'producto_id[]': [self.prod_1.id],
            'presentacion_id[]': [self.pres_base_1.id],
            'cantidad[]': ['1'],
            'porcentaje_descuento[]': ['0.00'],
        }
        resp = self.client.post(url, post_data)
        self.assertEqual(resp.status_code, 302)

        remito = Remito.objects.latest('id')
        # Debe haberse asignado vendedor_a (el asignado al cliente) y RECHAZADO vendedor_b
        self.assertEqual(remito.vendedor, self.vendedor_a)
        self.assertNotEqual(remito.vendedor, self.vendedor_b)

    # --------------------------------------------------------------------------
    # 5. Cliente sin vendedor con mensaje controlado (sin error 500)
    # --------------------------------------------------------------------------
    def test_cliente_sin_vendedor_con_mensaje_controlado(self):
        self.client.force_login(self.supervisor)
        url = reverse('gestion:remito_directo')

        post_data = {
            'cliente_id': self.cliente_sin_vendedor.id,
            'tipo_lista_precio_id': self.lista_minorista.id,
            'fecha': '2026-10-24',
            'codigo[]': ['00100'],
            'producto_id[]': [self.prod_1.id],
            'cantidad[]': ['2'],
            'porcentaje_descuento[]': ['0.00'],
        }
        resp = self.client.post(url, post_data)
        # No debe arrojar error 500, debe responder HTTP 200 re-renderizando con mensaje claro
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "no tiene un vendedor asignado")
        # Debe contener enlace autorizado a editar el cliente
        edit_url = reverse('gestion:cliente_editar', args=[self.cliente_sin_vendedor.id])
        self.assertContains(resp, edit_url)

        # No se debe haber creado ningún remito
        self.assertFalse(Remito.objects.filter(cliente=self.cliente_sin_vendedor).exists())

    # --------------------------------------------------------------------------
    # 6. Minorista predeterminada y selección de otra lista activa
    # --------------------------------------------------------------------------
    def test_minorista_predeterminada_y_seleccion_otra_lista(self):
        self.client.force_login(self.supervisor)
        url = reverse('gestion:remito_directo')

        # GET debe tener seleccionada por defecto la lista Minorista
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['default_lista'], self.lista_minorista)
        self.assertEqual(resp.context['selected_lista_id'], self.lista_minorista.id)

        # Emitir con Lista Mayorista seleccionada explícitamente
        post_data = {
            'cliente_id': self.cliente_con_vendedor.id,
            'tipo_lista_precio_id': self.lista_mayorista.id,
            'fecha': '2026-10-24',
            'codigo[]': ['00100'],
            'producto_id[]': [self.prod_1.id],
            'cantidad[]': ['1'],
            'porcentaje_descuento[]': ['0.00'],
        }
        resp_post = self.client.post(url, post_data)
        self.assertEqual(resp_post.status_code, 302)

        remito = Remito.objects.latest('id')
        self.assertEqual(remito.tipo_lista_precio, self.lista_mayorista)
        # El precio en el remito debe corresponder a la lista Mayorista ($847.00), no a Minorista ($1000.00)
        detalle = remito.detalles.first()
        self.assertEqual(detalle.precio_unitario_historico, Decimal('847.00'))

    # --------------------------------------------------------------------------
    # 7. Precio ausente, producto inválido y cantidad fraccionaria
    # --------------------------------------------------------------------------
    def test_precio_ausente_producto_invalido_y_cantidad_fraccionaria(self):
        self.client.force_login(self.supervisor)
        url = reverse('gestion:remito_directo')

        # Caso A: prod_2 no tiene precio en Lista Mayorista
        post_precio_ausente = {
            'cliente_id': self.cliente_con_vendedor.id,
            'tipo_lista_precio_id': self.lista_mayorista.id,
            'codigo[]': ['00200'],
            'producto_id[]': [self.prod_2.id],
            'cantidad[]': ['1'],
            'porcentaje_descuento[]': ['0.00'],
        }
        resp_a = self.client.post(url, post_precio_ausente)
        self.assertEqual(resp_a.status_code, 200)
        self.assertContains(resp_a, "no tiene precio definido en la lista")

        # Caso B: Código inexistente
        post_codigo_invalido = {
            'cliente_id': self.cliente_con_vendedor.id,
            'tipo_lista_precio_id': self.lista_minorista.id,
            'codigo[]': ['COD_INEXISTENTE'],
            'cantidad[]': ['1'],
            'porcentaje_descuento[]': ['0.00'],
        }
        resp_b = self.client.post(url, post_codigo_invalido)
        self.assertEqual(resp_b.status_code, 200)
        self.assertContains(resp_b, "no existe o se encuentra inactivo")

        # Caso C: Cantidad fraccionaria no se trunca silenciosamente
        post_fraccionaria = {
            'cliente_id': self.cliente_con_vendedor.id,
            'tipo_lista_precio_id': self.lista_minorista.id,
            'codigo[]': ['00100'],
            'producto_id[]': [self.prod_1.id],
            'cantidad[]': ['1.5'],
            'porcentaje_descuento[]': ['0.00'],
        }
        resp_c = self.client.post(url, post_fraccionaria)
        self.assertEqual(resp_c.status_code, 200)
        self.assertContains(resp_c, "No se permiten cantidades fraccionarias")

    # --------------------------------------------------------------------------
    # 8. Cálculo del caso testigo y coincidencia con comprobante e impresión
    # --------------------------------------------------------------------------
    def test_calculo_caso_testigo_y_coincidencia_con_impresion(self):
        """
        Caso Testigo del requerimiento:
        - Fila 1: precio 1.000, cantidad 3, descuento 10% -> bruto 3.000, descuento 300, total 2.700.
        - Fila 2: precio 2.000, cantidad 2, descuento 0%  -> bruto 4.000, descuento 0,   total 4.000.
        - Pie: subtotal 7.000, descuento 300, total general 6.700.
        """
        self.client.force_login(self.supervisor)
        url = reverse('gestion:remito_directo')

        post_data = {
            'cliente_id': self.cliente_con_vendedor.id,
            'tipo_lista_precio_id': self.lista_minorista.id,
            'fecha': '2026-10-24',
            'codigo[]': ['00100', '00200'],
            'producto_id[]': [self.prod_1.id, self.prod_2.id],
            'presentacion_id[]': [self.pres_base_1.id, self.pres_base_2.id],
            'cantidad[]': ['3', '2'],
            'porcentaje_descuento[]': ['10.00', '0.00'],
        }
        resp = self.client.post(url, post_data)
        self.assertEqual(resp.status_code, 302)

        remito = Remito.objects.latest('id')
        # Totales en cabecera
        self.assertEqual(remito.subtotal_bruto, Decimal('7000.00'))
        self.assertEqual(remito.total_descuento, Decimal('300.00'))
        self.assertEqual(remito.monto_total, Decimal('6700.00'))

        detalles = list(remito.detalles.order_by('id'))
        self.assertEqual(len(detalles), 2)

        # Fila 1
        d1 = detalles[0]
        self.assertEqual(d1.producto, self.prod_1)
        self.assertEqual(d1.precio_unitario_historico, Decimal('1000.00'))
        self.assertEqual(d1.cantidad, 3)
        self.assertEqual(d1.porcentaje_descuento, Decimal('10.00'))
        self.assertEqual(d1.subtotal, Decimal('2700.00'))

        # Fila 2
        d2 = detalles[1]
        self.assertEqual(d2.producto, self.prod_2)
        self.assertEqual(d2.precio_unitario_historico, Decimal('2000.00'))
        self.assertEqual(d2.cantidad, 2)
        self.assertEqual(d2.porcentaje_descuento, Decimal('0.00'))
        self.assertEqual(d2.subtotal, Decimal('4000.00'))

        # Vista de impresión A4
        url_impresion = reverse('comprobantes:imprimir_remito', args=[remito.id])
        resp_print = self.client.get(url_impresion)
        self.assertEqual(resp_print.status_code, 200)
        self.assertContains(resp_print, remito.numero_completo)
        self.assertContains(resp_print, "6700,00")
        self.assertContains(resp_print, "7000,00")
        self.assertContains(resp_print, "300,00")
        self.assertContains(resp_print, "24/10/2026")

    # --------------------------------------------------------------------------
    # 9. Preservación de valores ingresados tras errores de validación
    # --------------------------------------------------------------------------
    def test_preservacion_de_valores_tras_errores(self):
        self.client.force_login(self.supervisor)
        url = reverse('gestion:remito_directo')

        # Enviar datos válidos en fila 1 y un error en fila 2 (cantidad negativa)
        post_data = {
            'cliente_id': self.cliente_con_vendedor.id,
            'tipo_lista_precio_id': self.lista_minorista.id,
            'fecha': '2026-10-24',
            'observaciones': 'Observación intacta',
            'codigo[]': ['00100', '00200'],
            'producto_id[]': [self.prod_1.id, self.prod_2.id],
            'cantidad[]': ['5', '-2'],
            'porcentaje_descuento[]': ['15.00', '0.00'],
        }
        resp = self.client.post(url, post_data)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "La cantidad debe ser mayor a 0")

        # Verificar que el contexto conserve exactamente la cabecera y filas ingresadas
        self.assertEqual(resp.context['selected_cliente_id'], self.cliente_con_vendedor.id)
        self.assertEqual(resp.context['selected_lista_id'], self.lista_minorista.id)
        self.assertEqual(resp.context['observaciones'], 'Observación intacta')

        filas = resp.context['filas_recargadas']
        self.assertEqual(len(filas), 2)
        self.assertEqual(filas[0]['codigo'], '00100')
        self.assertEqual(filas[0]['cantidad'], '5')
        self.assertEqual(filas[0]['descuento'], '15.00')

    # --------------------------------------------------------------------------
    # 10. Integridad de numeración, stock y remitos originados en pedidos
    # --------------------------------------------------------------------------
    def test_integridad_numeracion_stock_y_remitos_desde_pedidos(self):
        # A. Stock y numeración por remito directo
        stock_inicial_1 = self.prod_1.stock_actual
        remito_directo = RemitoService.emitir_remito(
            cliente=self.cliente_con_vendedor,
            supervisor=self.supervisor,
            items=[{
                'producto': self.prod_1,
                'cantidad': 4,
                'factor_unidades': 1,
                'porcentaje_descuento': Decimal('0.00')
            }],
            tipo_lista_precio=self.lista_minorista
        )
        self.prod_1.refresh_from_db()
        self.assertEqual(self.prod_1.stock_actual, stock_inicial_1 - 4)

        # Movimiento de Kardex registrado
        mov = MovimientoStock.objects.filter(documento_referencia=remito_directo.numero_completo).first()
        self.assertIsNotNone(mov)
        self.assertEqual(mov.tipo_movimiento, 'SALIDA_REMITO')
        self.assertEqual(mov.cantidad, -4)

        # B. Integridad de remito originado en un Pedido con precio congelado
        pedido = Pedido.objects.create(
            numero_pedido='PED-007-001',
            cliente=self.cliente_con_vendedor,
            vendedor=self.vendedor_a,
            estado='APROBADO',
            total_estimado=Decimal('3333.00')
        )
        det_ped = DetallePedido.objects.create(
            pedido=pedido,
            producto=self.prod_1,
            cantidad=2,
            precio_unitario=Decimal('3333.00'),  # Precio especial congelado en el pedido
            subtotal=Decimal('6666.00')
        )

        remito_pedido = RemitoService.emitir_remito_desde_pedido(pedido, self.supervisor)
        remito_pedido.refresh_from_db()

        # El remito del pedido debe conservar el precio congelado del pedido ($3333.00)
        det_remito = remito_pedido.detalles.first()
        self.assertEqual(det_remito.precio_unitario_historico, Decimal('3333.00'))
        self.assertEqual(det_remito.subtotal, Decimal('6666.00'))
        self.assertEqual(remito_pedido.monto_total, Decimal('6666.00'))

        # Correlativo numerado secuencial
        self.assertEqual(remito_pedido.numero, remito_directo.numero + 1)
