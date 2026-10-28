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
        from django.utils import timezone
        self.assertEqual(timezone.localtime(remito.fecha_emision).date(), timezone.localdate())

        # Compatibilidad retroactiva: remito histórico con fecha=None
        remito.fecha = None
        remito.save(update_fields=['fecha'])
        remito.refresh_from_db()
        self.assertIsNone(remito.fecha)
        self.assertEqual(remito.fecha_comercial, timezone.localtime(remito.fecha_emision).date())

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
    # 5. Cliente sin vendedor emite remito exitosamente (asociación opcional)
    # --------------------------------------------------------------------------
    def test_cliente_sin_vendedor_emite_remito_exitosamente(self):
        """
        Regla de negocio:
        La asociación cliente-vendedor es opcional. Un cliente sin vendedor debe poder emitir remitos.
        - 'Vendedor Responsable' y avisos de asignar vendedor fueron removidos de la interfaz.
        - El remito conserva vendedor=None sin sustituirlo por el supervisor que lo emite.
        - Stock, descuentos, fecha y lista de precios se calculan y descuentan correctamente.
        - La impresión y listados funcionan correctamente mostrando 'Sin vendedor'.
        """
        self.client.force_login(self.supervisor)
        url = reverse('gestion:remito_directo')

        # Verificar que el formulario no muestre Vendedor Responsable ni botón Asignar
        resp_get = self.client.get(url)
        self.assertEqual(resp_get.status_code, 200)
        self.assertNotContains(resp_get, "Vendedor Responsable")
        self.assertNotContains(resp_get, "Sin vendedor asignado")

        stock_inicial = self.prod_1.stock_actual
        fecha_comercial = '2026-10-25'
        post_data = {
            'cliente_id': self.cliente_sin_vendedor.id,
            'tipo_lista_precio_id': self.lista_minorista.id,
            'fecha': fecha_comercial,
            'codigo[]': ['00100'],
            'producto_id[]': [self.prod_1.id],
            'cantidad[]': ['2'],
            'porcentaje_descuento[]': ['10.00'],
        }
        resp = self.client.post(url, post_data)
        self.assertEqual(resp.status_code, 302)

        remito = Remito.objects.latest('id')
        self.assertEqual(remito.cliente, self.cliente_sin_vendedor)
        # Vendedor debe ser None (no sustituido por el supervisor)
        self.assertIsNone(remito.vendedor)
        self.assertEqual(remito.supervisor, self.supervisor)
        self.assertNotEqual(remito.vendedor, self.supervisor)

        # Stock, descuentos, fecha y lista de precios
        self.prod_1.refresh_from_db()
        self.assertEqual(self.prod_1.stock_actual, stock_inicial - 2)
        self.assertEqual(str(remito.fecha), fecha_comercial)
        self.assertEqual(remito.tipo_lista_precio, self.lista_minorista)
        self.assertEqual(remito.subtotal_bruto, Decimal('2000.00'))
        self.assertEqual(remito.total_descuento, Decimal('200.00'))
        self.assertEqual(remito.monto_total, Decimal('1800.00'))

        # Vista de impresión A4 funciona con vendedor vacío y no muestra datos de vendedor ni firmas
        resp_print = self.client.get(reverse('comprobantes:imprimir_remito', args=[remito.id]))
        self.assertEqual(resp_print.status_code, 200)
        self.assertNotContains(resp_print, "Sin vendedor")
        self.assertNotContains(resp_print, "Vendedor:")
        self.assertNotContains(resp_print, "Firma Recepción Conforme")
        self.assertContains(resp_print, "1800,00")

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

    # --------------------------------------------------------------------------
    # 11. DIST-007A: Fila vacía inicial se ignora y emite 1 solo detalle
    # --------------------------------------------------------------------------
    def test_dist007a_fila_final_vacia_con_valores_iniciales_se_ignora(self):
        """
        DIST-007A (Punto 1):
        crearFila() inicia cantidad=1 y descuento=0.00.
        Una fila final sin producto ni código y con valores iniciales debe ser ignorada
        consistentemente como fila vacía, emitiendo un solo detalle.
        """
        self.client.force_login(self.supervisor)
        url = reverse('gestion:remito_directo')

        post_data = {
            'cliente_id': self.cliente_con_vendedor.id,
            'tipo_lista_precio_id': self.lista_minorista.id,
            'fecha': '2026-10-24',
            # Fila 1: Producto válido; Fila 2: Fila final vacía con valores iniciales por defecto
            'codigo[]': ['00100', ''],
            'producto_id[]': [str(self.prod_1.id), ''],
            'presentacion_id[]': [str(self.pres_base_1.id), ''],
            'cantidad[]': ['3', '1'],
            'porcentaje_descuento[]': ['0.00', '0.00'],
        }
        resp = self.client.post(url, post_data)
        self.assertEqual(resp.status_code, 302)

        remito = Remito.objects.latest('id')
        self.assertEqual(remito.detalles.count(), 1)
        det = remito.detalles.first()
        self.assertEqual(det.producto, self.prod_1)
        self.assertEqual(det.cantidad, 3)

    # --------------------------------------------------------------------------
    # 12. DIST-007A: Precios exclusivamente del server y lista obligatoria
    # --------------------------------------------------------------------------
    def test_dist007a_precios_exclusivamente_del_servidor_y_rechazo_lista_ausente_invalida(self):
        """
        DIST-007A (Punto 2):
        - Intento de enviar precios manipulados por POST es ignorado; se resuelve estrictamente del server.
        - Exige lista activa válida. Si falta o es inválida, se rechaza y no se sustituye silenciosamente.
        """
        self.client.force_login(self.supervisor)
        url = reverse('gestion:remito_directo')

        # Caso A: Precio manipulado en POST ($1.00 en vez de $1000.00 de lista)
        post_manipulado = {
            'cliente_id': self.cliente_con_vendedor.id,
            'tipo_lista_precio_id': self.lista_minorista.id,
            'fecha': '2026-10-24',
            'codigo[]': ['00100'],
            'producto_id[]': [str(self.prod_1.id)],
            'cantidad[]': ['2'],
            'porcentaje_descuento[]': ['0.00'],
            'precio_unitario[]': ['1.00'],  # Manipulación maliciosa
        }
        resp_a = self.client.post(url, post_manipulado)
        self.assertEqual(resp_a.status_code, 302)
        remito_a = Remito.objects.latest('id')
        det_a = remito_a.detalles.first()
        # Debe haber tomado el precio oficial del servidor ($1000.00) ignorando el $1.00
        self.assertEqual(det_a.precio_unitario_historico, Decimal('1000.00'))
        self.assertEqual(remito_a.monto_total, Decimal('2000.00'))

        # Caso B: Lista ausente (no debe sustituir por la del cliente)
        count_antes = Remito.objects.count()
        post_sin_lista = {
            'cliente_id': self.cliente_con_vendedor.id,
            'tipo_lista_precio_id': '',  # Ausente
            'codigo[]': ['00100'],
            'producto_id[]': [str(self.prod_1.id)],
            'cantidad[]': ['1'],
            'porcentaje_descuento[]': ['0.00'],
        }
        resp_b = self.client.post(url, post_sin_lista)
        self.assertEqual(resp_b.status_code, 200)
        self.assertContains(resp_b, "Debe seleccionar una lista de precios activa válida.")
        self.assertEqual(Remito.objects.count(), count_antes)

        # Caso C: Lista inválida / inexistente
        post_lista_invalida = {
            'cliente_id': self.cliente_con_vendedor.id,
            'tipo_lista_precio_id': '999999',  # Inexistente
            'codigo[]': ['00100'],
            'producto_id[]': [str(self.prod_1.id)],
            'cantidad[]': ['1'],
            'porcentaje_descuento[]': ['0.00'],
        }
        resp_c = self.client.post(url, post_lista_invalida)
        self.assertEqual(resp_c.status_code, 200)
        self.assertContains(resp_c, "Debe seleccionar una lista de precios activa válida.")
        self.assertEqual(Remito.objects.count(), count_antes)

    # --------------------------------------------------------------------------
    # 13. DIST-007A: Coherencia código/producto y rechazo presentación inválida
    # --------------------------------------------------------------------------
    def test_dist007a_coherencia_codigo_producto_y_rechazo_presentacion_invalida(self):
        """
        DIST-007A (Punto 3):
        - Si código e ID difieren, el backend rechaza la incoherencia.
        - Si se envía presentación inexistente o de otro producto, rechaza en vez de convertir a base.
        """
        self.client.force_login(self.supervisor)
        url = reverse('gestion:remito_directo')
        count_antes = Remito.objects.count()

        # Caso A: Código de prod_1 pero producto_id de prod_2
        post_incoherente = {
            'cliente_id': self.cliente_con_vendedor.id,
            'tipo_lista_precio_id': self.lista_minorista.id,
            'codigo[]': [self.prod_1.codigo],
            'producto_id[]': [str(self.prod_2.id)],
            'cantidad[]': ['1'],
            'porcentaje_descuento[]': ['0.00'],
        }
        resp_a = self.client.post(url, post_incoherente)
        self.assertEqual(resp_a.status_code, 200)
        self.assertContains(resp_a, "Incoherencia entre el código")
        self.assertEqual(Remito.objects.count(), count_antes)

        # Caso B: Presentación de otro producto (pres_pack_2 enviada en renglón de prod_1)
        post_pres_ajena = {
            'cliente_id': self.cliente_con_vendedor.id,
            'tipo_lista_precio_id': self.lista_minorista.id,
            'codigo[]': [self.prod_1.codigo],
            'producto_id[]': [str(self.prod_1.id)],
            'presentacion_id[]': [str(self.pres_pack_2.id)],  # Pertenece a prod_2, NO a prod_1
            'cantidad[]': ['1'],
            'porcentaje_descuento[]': ['0.00'],
        }
        resp_b = self.client.post(url, post_pres_ajena)
        self.assertEqual(resp_b.status_code, 200)
        self.assertContains(resp_b, "no existe o no pertenece a este producto")
        self.assertEqual(Remito.objects.count(), count_antes)

    # --------------------------------------------------------------------------
    # 14. DIST-007A: Presentación alternativa con factor > 1
    # --------------------------------------------------------------------------
    def test_dist007a_presentacion_alternativa_factor_mayor_a_uno(self):
        """
        DIST-007A (Punto 3):
        Prueba con presentación alternativa y factor mayor a uno (Pack x6 de Agua Mineral 2L).
        Precio base = 2000.00 -> Precio pack = 12000.00.
        Cantidad = 2 packs -> Subtotal = 24000.00, descuento stock = 12 unidades.
        """
        self.client.force_login(self.supervisor)
        url = reverse('gestion:remito_directo')
        stock_inicial_2 = self.prod_2.stock_actual

        post_data = {
            'cliente_id': self.cliente_con_vendedor.id,
            'tipo_lista_precio_id': self.lista_minorista.id,
            'codigo[]': [self.prod_2.codigo],
            'producto_id[]': [str(self.prod_2.id)],
            'presentacion_id[]': [str(self.pres_pack_2.id)],  # Factor 6
            'cantidad[]': ['2'],
            'porcentaje_descuento[]': ['0.00'],
        }
        resp = self.client.post(url, post_data)
        self.assertEqual(resp.status_code, 302)

        remito = Remito.objects.latest('id')
        detalle = remito.detalles.first()
        self.assertEqual(detalle.presentacion, self.pres_pack_2)
        self.assertEqual(detalle.factor_unidades, 6)
        self.assertEqual(detalle.precio_unitario_historico, Decimal('12000.00'))
        self.assertEqual(detalle.subtotal, Decimal('24000.00'))

        self.prod_2.refresh_from_db()
        self.assertEqual(self.prod_2.stock_actual, stock_inicial_2 - 12)

    # --------------------------------------------------------------------------
    # 15. DIST-007A: Escape seguro de datos HTML y caracteres especiales
    # --------------------------------------------------------------------------
    def test_dist007a_escape_seguro_caracteres_especiales_html(self):
        """
        DIST-007A (Punto 5):
        Escape seguro de datos con json_script y format_html:
        Verifica que productos y clientes con caracteres especiales y HTML
        (ej: <script>, <b>, &, ", ') se serialicen y escapen sin vulnerabilidades XSS.
        """
        self.client.force_login(self.supervisor)
        url = reverse('gestion:remito_directo')

        # Crear producto con contenido semejante a HTML y comillas
        prod_xss = Producto.objects.create(
            codigo='XSS-001',
            nombre='Alfajor <script>alert("xss")</script> & "Especial"',
            categoria=self.categoria,
            marca=self.marca,
            costo_base=Decimal('100.00'),
            stock_actual=50,
            activo=True
        )
        PrecioProducto.objects.create(
            producto=prod_xss,
            tipo_lista=self.lista_minorista,
            precio_final=Decimal('150.00')
        )

        resp_get = self.client.get(url)
        self.assertEqual(resp_get.status_code, 200)
        # El script json_script no debe contener el tag <script> sin escapar
        content = resp_get.content.decode('utf-8')
        self.assertIn('catalogDataScript', content)
        self.assertNotIn('<script>alert("xss")</script>', content)
        self.assertIn(r'\u003Cscript\u003Ealert(\"xss\")\u003C/script\u003E', content)

        # Crear cliente sin vendedor con caracteres especiales y HTML en razón social
        cliente_xss = Cliente.objects.create(
            cuit='30333333334',
            razon_social='Supermercado <img src=x onerror=alert(1)> & "Amigo"',
            zona=self.zona,
            localidad=self.localidad,
            vendedor=None,
            tipo_lista_precio=self.lista_minorista,
            activo=True
        )

        # En el selector de clientes, la razón social con caracteres especiales y HTML debe escaparse
        resp_get_xss = self.client.get(url)
        self.assertEqual(resp_get_xss.status_code, 200)
        self.assertContains(resp_get_xss, '&lt;img src=x onerror=alert(1)&gt; &amp; &quot;Amigo&quot;')
        self.assertNotContains(resp_get_xss, '<img src=x onerror=alert(1)>')

        # Y al emitir el remito con cliente_xss (sin vendedor), la impresión debe escapar el nombre del cliente
        post_data = {
            'cliente_id': cliente_xss.id,
            'tipo_lista_precio_id': self.lista_minorista.id,
            'codigo[]': ['XSS-001'],
            'producto_id[]': [str(prod_xss.id)],
            'cantidad[]': ['1'],
            'porcentaje_descuento[]': ['0.00'],
        }
        resp_post = self.client.post(url, post_data)
        self.assertEqual(resp_post.status_code, 302)
        remito_xss = Remito.objects.latest('id')
        resp_print = self.client.get(reverse('comprobantes:imprimir_remito', args=[remito_xss.id]))
        self.assertEqual(resp_print.status_code, 200)
        self.assertContains(resp_print, '&lt;img src=x onerror=alert(1)&gt; &amp; &quot;Amigo&quot;')
        self.assertNotContains(resp_print, '<img src=x onerror=alert(1)>')

    # --------------------------------------------------------------------------
    # 16. Paginación A4: ítem con descripción extremadamente larga
    # --------------------------------------------------------------------------
    def test_paginacion_item_descripcion_extremadamente_larga(self):
        """
        Verifica que un renglón con descripción técnica extensa (800 caracteres)
        se procese sin bucle infinito, consuma al menos un ítem por iteración,
        aparezca exactamente una vez en orden y los totales figuren solo al pie
        de la última página.
        """
        self.client.force_login(self.supervisor)
        desc_larga = "DESCRIPCIÓN INDUSTRIAL EXTENSA - " + ("COMPONENTE QUÍMICO REFORZADO " * 25)
        prod_largo = Producto.objects.create(
            codigo='LNG-001',
            nombre=desc_larga[:800],
            categoria=self.categoria,
            marca=self.marca,
            alicuota_iva=Decimal('0.00'),
            costo_base=Decimal('100.00'),
            stock_actual=100,
            controla_stock=True,
            activo=True
        )
        Presentacion.objects.create(
            producto=prod_largo,
            nombre='Unidad',
            factor_conversion=1,
            es_default=True
        )
        PrecioProducto.objects.create(
            producto=prod_largo,
            tipo_lista=self.lista_minorista,
            precio_neto=Decimal('150.00'),
            precio_final=Decimal('150.00')
        )

        url = reverse('gestion:remito_directo')
        post_data = {
            'cliente_id': self.cliente_con_vendedor.id,
            'tipo_lista_precio_id': self.lista_minorista.id,
            'fecha': '2026-10-27',
            'codigo[]': ['00100', 'LNG-001', '00200'],
            'producto_id[]': [str(self.prod_1.id), str(prod_largo.id), str(self.prod_2.id)],
            'cantidad[]': ['1', '2', '3'],
            'porcentaje_descuento[]': ['0.00', '5.00', '0.00'],
        }
        resp_post = self.client.post(url, post_data)
        self.assertEqual(resp_post.status_code, 302)

        remito = Remito.objects.latest('id')
        resp_print = self.client.get(reverse('comprobantes:imprimir_remito', args=[remito.id]))
        self.assertEqual(resp_print.status_code, 200)

        paginas = resp_print.context['paginas']
        self.assertGreaterEqual(len(paginas), 1)

        # Unicidad y orden estricto de cada producto
        items_en_paginas = [item for p in paginas for item in p['items']]
        detalles_remito = list(remito.detalles.all().order_by('id'))
        self.assertEqual(len(items_en_paginas), len(detalles_remito))
        for item_pag, detalle in zip(items_en_paginas, detalles_remito):
            self.assertEqual(item_pag.id, detalle.id)
            self.assertEqual(item_pag.codigo_historico, detalle.codigo_historico)

        # Totales solo en la última página
        for p in paginas[:-1]:
            self.assertFalse(p['show_totals'])
        self.assertTrue(paginas[-1]['show_totals'])

    # --------------------------------------------------------------------------
    # 17. Paginación A4: observaciones multilínea y comprobante multipágina
    # --------------------------------------------------------------------------
    def test_paginacion_observaciones_multilinea_y_multipagina(self):
        """
        Verifica que observaciones comerciales de varios renglones adapten
        dinámicamente el espacio de la página 1 sin generar solapamientos,
        preservando el orden y la unicidad de los productos.
        """
        self.client.force_login(self.supervisor)
        obs_texto = (
            "Instrucciones de descarga en planta:\n"
            "1. Presentar remito original en guardia de acceso.\n"
            "2. Vehículo habilitado con seguro de carga y EPP completo.\n"
            "3. Descarga exclusiva en rampa B sector refrigerados.\n"
            "4. Contactar a recepción antes de las 14:00 hs."
        )

        url = reverse('gestion:remito_directo')
        post_data = {
            'cliente_id': self.cliente_con_vendedor.id,
            'tipo_lista_precio_id': self.lista_minorista.id,
            'fecha': '2026-10-27',
            'observaciones': obs_texto,
            'codigo[]': ['00100', '00200'],
            'producto_id[]': [str(self.prod_1.id), str(self.prod_2.id)],
            'cantidad[]': ['5', '10'],
            'porcentaje_descuento[]': ['0.00', '0.00'],
        }
        resp_post = self.client.post(url, post_data)
        self.assertEqual(resp_post.status_code, 302)

        remito = Remito.objects.latest('id')
        self.assertEqual(remito.observaciones, obs_texto)

        resp_print = self.client.get(reverse('comprobantes:imprimir_remito', args=[remito.id]))
        self.assertEqual(resp_print.status_code, 200)
        self.assertContains(resp_print, "Instrucciones de descarga en planta:")
        self.assertContains(resp_print, "Contactar a recepción antes de las 14:00 hs.")

        paginas = resp_print.context['paginas']
        items_en_paginas = [item for p in paginas for item in p['items']]
        detalles_remito = list(remito.detalles.all().order_by('id'))
        self.assertEqual(len(items_en_paginas), len(detalles_remito))
        for item_pag, detalle in zip(items_en_paginas, detalles_remito):
            self.assertEqual(item_pag.id, detalle.id)

        self.assertTrue(paginas[-1]['show_totals'])

    # --------------------------------------------------------------------------
    # 18. Paginación A4: comprobante de varias páginas (35 renglones)
    # --------------------------------------------------------------------------
    def test_paginacion_multipagina_35_renglones(self):
        """
        Verifica un remito extenso con 35 renglones:
        - Se divide en múltiples páginas sin perder ni duplicar productos.
        - Cada producto aparece exactamente una vez y en orden correlativo.
        - Los totales se renderizan única y exclusivamente al pie de la última hoja.
        """
        self.client.force_login(self.supervisor)
        prods_creados = []
        for i in range(35):
            p = Producto.objects.create(
                codigo=f'MLT-{i+1:03d}',
                nombre=f'Producto multipágina comercial en formato A4 renglón #{i+1:02d} descripción extendida para control de salto',
                categoria=self.categoria,
                marca=self.marca,
                alicuota_iva=Decimal('0.00'),
                costo_base=Decimal('50.00'),
                stock_actual=100,
                controla_stock=True,
                activo=True
            )
            Presentacion.objects.create(
                producto=p,
                nombre='Unidad',
                factor_conversion=1,
                es_default=True
            )
            PrecioProducto.objects.create(
                producto=p,
                tipo_lista=self.lista_minorista,
                precio_neto=Decimal('80.00'),
                precio_final=Decimal('80.00')
            )
            prods_creados.append(p)

        url = reverse('gestion:remito_directo')
        post_data = {
            'cliente_id': self.cliente_sin_vendedor.id,
            'tipo_lista_precio_id': self.lista_minorista.id,
            'fecha': '2026-10-27',
            'codigo[]': [p.codigo for p in prods_creados],
            'producto_id[]': [str(p.id) for p in prods_creados],
            'cantidad[]': ['1'] * 35,
            'porcentaje_descuento[]': ['0.00'] * 35,
        }
        resp_post = self.client.post(url, post_data)
        self.assertEqual(resp_post.status_code, 302)

        remito = Remito.objects.latest('id')
        self.assertEqual(remito.detalles.count(), 35)

        resp_print = self.client.get(reverse('comprobantes:imprimir_remito', args=[remito.id]))
        self.assertEqual(resp_print.status_code, 200)

        paginas = resp_print.context['paginas']
        self.assertGreaterEqual(len(paginas), 2)

        # Unicidad y orden
        items_en_paginas = [item for p in paginas for item in p['items']]
        detalles_remito = list(remito.detalles.all().order_by('id'))
        self.assertEqual(len(items_en_paginas), 35)
        for idx, (item_pag, detalle) in enumerate(zip(items_en_paginas, detalles_remito)):
            self.assertEqual(item_pag.id, detalle.id)
            self.assertEqual(item_pag.codigo_historico, f'MLT-{idx+1:03d}')

        # Totales solo en la última página
        for p in paginas[:-1]:
            self.assertFalse(p['show_totals'])
        self.assertTrue(paginas[-1]['show_totals'])

        # Verificar llenado voraz: la primera hoja aprovecha toda su capacidad disponible
        # y ningún producto de la segunda hoja hubiera cabido al final de la primera hoja
        import math
        def est_h(d):
            chars = len(d.descripcion_historica or '')
            lines = max(1, math.ceil(chars / 60.0))
            h = 5.29 + (lines - 1) * 3.8
            if (d.porcentaje_descuento or 0) > 0:
                h += 3.6
            return h

        accum_h_p1 = sum(est_h(it) for it in paginas[0]['items'])
        cap_p1_inter = 268.0 - (52.3 + 6.61)  # 209.09 mm sin observaciones
        espacio_libre_p1 = cap_p1_inter - accum_h_p1
        altura_primer_item_p2 = est_h(paginas[1]['items'][0])
        self.assertGreater(
            altura_primer_item_p2,
            espacio_libre_p1,
            "El primer ítem de la segunda hoja no debía caber en el espacio libre restante de la primera hoja."
        )
        self.assertGreater(len(paginas[0]['items']), len(paginas[1]['items']))

    # --------------------------------------------------------------------------
    # 19. Paginación A4: renglón más alto que el área imprimible (error controlado)
    # --------------------------------------------------------------------------
    def test_paginacion_item_excede_altura_maxima_error_controlado(self):
        """
        Verifica que si un ítem supera el área imprimible máxima de una página A4,
        el sistema no se cuelgue en bucle infinito y responda con una salida controlada.
        """
        from comprobantes.services import calcular_paginacion_remito_a4

        class MockDetalleExtremo:
            codigo_historico = "ERR-EXTREMO"
            descripcion_historica = "X" * 5000  # Más de 80 líneas esperadas
            cantidad = 1
            precio_unitario_historico = Decimal('100.00')
            factor_unidades = 1
            presentacion = None
            presentacion_nombre = None
            porcentaje_descuento = Decimal('0.00')

        with self.assertRaises(ValueError) as ctx:
            calcular_paginacion_remito_a4([MockDetalleExtremo()])
        self.assertIn("supera la altura máxima imprimible", str(ctx.exception))

    # --------------------------------------------------------------------------
    # 20. Paginación A4: ítem que supera la primera hoja pero cabe en continuación
    # --------------------------------------------------------------------------
    def test_paginacion_item_supera_primera_hoja_pero_cabe_en_continuacion(self):
        """
        Verifica que si un ítem no cabe en la primera hoja por el espacio que ocupan el
        encabezado y los datos del cliente, pasa limpiamente a la hoja de continuación
        donde la capacidad disponible es mayor, sin caer en bucles ni arrojar error.
        """
        from comprobantes.services import calcular_paginacion_remito_a4
        import math

        # Un ítem de 3420 caracteres (~57 líneas) genera una altura estimada de ~218 mm.
        # En la primera hoja la capacidad es ~204 mm (no cabe).
        # En la hoja subsiguiente la capacidad es ~253.6 mm (sí cabe).
        class MockDetalleGrande:
            codigo_historico = "GRD-001"
            descripcion_historica = "A" * 3420
            cantidad = 1
            precio_unitario_historico = Decimal('100.00')
            factor_unidades = 1
            presentacion = None
            presentacion_nombre = None
            porcentaje_descuento = Decimal('0.00')

        item = MockDetalleGrande()
        paginas = calcular_paginacion_remito_a4([item], observaciones="Entrega en depósito central")

        self.assertEqual(len(paginas), 2)
        # Hoja 1: encabezado y datos de cliente, sin ítems, completa con casilleros vacíos
        self.assertTrue(paginas[0]['is_first'])
        self.assertFalse(paginas[0]['is_last'])
        self.assertEqual(len(paginas[0]['items']), 0)
        self.assertGreater(len(paginas[0]['empty_rows_range']), 0)
        self.assertFalse(paginas[0]['show_totals'])

        # Hoja 2: ítem grande ubicado en continuación con totales al pie
        self.assertFalse(paginas[1]['is_first'])
        self.assertTrue(paginas[1]['is_last'])
        self.assertEqual(len(paginas[1]['items']), 1)
        self.assertEqual(paginas[1]['items'][0].codigo_historico, "GRD-001")
        self.assertTrue(paginas[1]['show_totals'])

    # --------------------------------------------------------------------------
    # 21. Paginación A4: observaciones excesivas controladas
    # --------------------------------------------------------------------------
    def test_paginacion_observaciones_excesivas_error_controlado(self):
        """
        Verifica que observaciones comerciales desmedidas no produzcan capacidades negativas
        ni errores de división por cero, arrojando una excepción ValueError controlada.
        """
        from comprobantes.services import calcular_paginacion_remito_a4

        class MockDetalleNormal:
            codigo_historico = "NRM-001"
            descripcion_historica = "Producto habitual"
            cantidad = 1
            precio_unitario_historico = Decimal('50.00')
            factor_unidades = 1
            presentacion = None
            presentacion_nombre = None
            porcentaje_descuento = Decimal('0.00')

        obs_desmedidas = "Línea de observación larguísima.\n" * 150
        with self.assertRaises(ValueError) as ctx:
            calcular_paginacion_remito_a4([MockDetalleNormal()], observaciones=obs_desmedidas)
        self.assertIn("observaciones comerciales es demasiado extenso", str(ctx.exception))
