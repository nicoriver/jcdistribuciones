from decimal import Decimal
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model

from geografia.models import Provincia, Localidad, Zona
from clientes.models import Vendedor, Cliente
from productos.models import Categoria, Marca, Producto, Presentacion, TipoListaPrecio
from productos.services import CalculadoraPreciosService
from pedidos.models import Pedido, DetallePedido
from pedidos.services import PedidoService
from comprobantes.models import Remito
from stock.models import MovimientoStock

Usuario = get_user_model()


class CircuitoPedidosPreventaTests(TestCase):
    """
    Pruebas unitarias e integrales del Módulo 6 (Circuito de Pedidos y Preventa -> Remito A4).
    """

    def setUp(self):
        # 1. Usuarios de distintos roles
        self.supervisor = Usuario.objects.create_user(
            username='sup_pedidos',
            cuit_dni='20310000019',
            password='Password123!',
            nombre='Carlos',
            apellido='Supervisor',
            rol='SUPERVISOR'
        )
        self.user_vendedor = Usuario.objects.create_user(
            username='vend_pedidos',
            cuit_dni='20310000027',
            password='Password123!',
            nombre='Martín',
            apellido='Vendedor',
            rol='VENDEDOR'
        )

        # 2. Geografía, Vendedor, Lista y Cliente
        self.provincia = Provincia.objects.create(nombre='Entre Ríos')
        self.localidad = Localidad.objects.create(
            provincia=self.provincia,
            nombre='Concordia',
            codigo_postal='3200'
        )
        self.zona = Zona.objects.create(
            nombre='Zona Norte Preventa',
            dia_reparto_defecto='Martes y Viernes',
            activa=True
        )
        self.vendedor = Vendedor.objects.create(
            usuario=self.user_vendedor,
            nombre='Martín',
            apellido='Vendedor',
            legajo='VEND-601',
            comision_porcentaje=Decimal('4.00'),
            activo=True
        )

        self.lista_mayorista = TipoListaPrecio.objects.create(
            nombre='Lista Mayorista Preventa',
            descripcion='Lista para preventa mayorista',
            activa=True
        )

        self.cliente = Cliente.objects.create(
            cuit='30719988776',
            razon_social='Autoservicio El Sol SRL',
            nombre_fantasia='El Sol',
            domicilio='Av. San Lorenzo 850',
            localidad=self.localidad,
            zona=self.zona,
            vendedor=self.vendedor,
            tipo_lista_precio=self.lista_mayorista,
            activo=True
        )

        # 3. Catálogo de Productos y Presentaciones
        self.categoria = Categoria.objects.create(nombre='Almacén Mayorista', activa=True)
        self.marca = Marca.objects.create(nombre='Marolio', activa=True)
        self.producto = Producto.objects.create(
            codigo='ALM-900',
            nombre='Puré de Tomate 520g',
            categoria=self.categoria,
            marca=self.marca,
            costo_base=Decimal('800.00'),
            alicuota_iva=Decimal('21.00'),
            controla_stock=True,
            stock_actual=120,
            punto_reposicion=24,
            activo=True
        )
        self.presentacion_pack = Presentacion.objects.create(
            producto=self.producto,
            nombre='Pack x 12 Unidades',
            factor_conversion=12,
            codigo_barras='7799000120001'
        )
        CalculadoraPreciosService.actualizar_precios_producto(self.producto)

    def test_ciclo_estados_pedido_y_facturacion_a_remito_sin_doble_facturacion(self):
        """
        Verifica:
        1. Creación de Pedido en BORRADOR -> PENDIENTE_REVISION -> APROBADO por Vendedor (con ajuste de descuento).
        2. El stock NO se descuenta durante BORRADOR, PENDIENTE_REVISION ni APROBADO.
        3. Al ejecutar facturar_pedido_a_remito:
           - Se genera el Remito A4 comercial con numeración correlativa.
           - Se descuenta el stock físico exactamente una vez (3 packs x 12 = 36 unidades).
           - El Pedido pasa a estado FACTURADO_REMITO y guarda remito_asociado_id.
        4. Intentar facturar nuevamente el mismo pedido lanza ValidationError (impide doble facturación).
        """
        # 1. Crear pedido en BORRADOR y agregar 3 Packs x 12 unidades a $10.000 por pack
        pedido = Pedido.objects.create(
            cliente=self.cliente,
            vendedor=self.vendedor,
            lista_precio=self.lista_mayorista,
            estado='BORRADOR',
            observaciones='Entregar por la mañana'
        )
        detalle = DetallePedido.objects.create(
            pedido=pedido,
            producto=self.producto,
            presentacion=self.presentacion_pack,
            factor_unidades=12,
            cantidad=3,
            precio_unitario=Decimal('10000.00'),
            porcentaje_descuento=Decimal('0.00')
        )
        pedido.recalcular_totales()
        self.assertEqual(pedido.total_estimado, Decimal('30000.00'))

        # 2. Enviar a revisión
        PedidoService.enviar_a_revision(pedido)
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, 'PENDIENTE_REVISION')

        # 3. Aprobar por el Vendedor aplicando un 10% de descuento en el renglón
        PedidoService.aprobar_pedido(
            pedido=pedido,
            usuario=self.user_vendedor,
            descuentos_por_renglon={detalle.id: Decimal('10.00')}
        )
        pedido.refresh_from_db()
        detalle.refresh_from_db()
        self.assertEqual(pedido.estado, 'APROBADO')
        self.assertEqual(detalle.porcentaje_descuento, Decimal('10.00'))
        self.assertEqual(detalle.subtotal, Decimal('27000.00'))
        self.assertEqual(pedido.total_estimado, Decimal('27000.00'))

        # Verificar que antes de emitir el Remito el stock sigue intacto en 120
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.stock_actual, 120)

        # 4. Supervisor factura el pedido a Remito A4
        remito = PedidoService.facturar_pedido_a_remito(pedido=pedido, supervisor=self.supervisor)

        pedido.refresh_from_db()
        self.producto.refresh_from_db()

        self.assertEqual(pedido.estado, 'FACTURADO_REMITO')
        self.assertEqual(pedido.remito_asociado_id, remito.id)
        self.assertEqual(remito.numero_completo, 'R-0001-00000001')
        self.assertEqual(remito.total_comercial, Decimal('27000.00'))

        # Stock descontado: 120 - (3 packs * 12 u.) = 84 unidades
        self.assertEqual(self.producto.stock_actual, 84)

        # Kardex registrado
        mov = MovimientoStock.objects.filter(
            producto=self.producto,
            tipo_movimiento__in=['SALIDA_REMITO', 'SALIDA_VENTA']
        ).first()
        self.assertIsNotNone(mov)
        self.assertEqual(mov.cantidad, -36)
        self.assertEqual(mov.stock_anterior, 120)
        self.assertEqual(mov.stock_resultante, 84)

        # 5. Impedir doble facturación
        with self.assertRaises(ValidationError):
            PedidoService.facturar_pedido_a_remito(pedido=pedido, supervisor=self.supervisor)

        # El stock y la cantidad de remitos no deben alterarse tras el intento fallido
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.stock_actual, 84)
        self.assertEqual(Remito.objects.count(), 1)

    def test_rechazar_pedido_registra_motivo(self):
        """
        Verifica la transición de rechazo de un pedido con motivo obligatorio.
        """
        pedido = Pedido.objects.create(
            cliente=self.cliente,
            vendedor=self.vendedor,
            lista_precio=self.lista_mayorista,
            estado='PENDIENTE_REVISION'
        )
        PedidoService.rechazar_pedido(pedido, motivo='Cliente supera límite de crédito acordado')
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, 'RECHAZADO')
        self.assertEqual(pedido.motivo_rechazo, 'Cliente supera límite de crédito acordado')
