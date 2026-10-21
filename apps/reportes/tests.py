from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from usuarios.models import Usuario
from clientes.models import Cliente, Vendedor, Zona, CondicionIVA
from productos.models import Categoria, AlicuotaIVA, Producto, ListaPrecio, PrecioProducto, Presentacion
from pedidos.services import PedidoService
from comprobantes.services import ComprobanteService
from reportes.services import LogisticaService


class ReportesTestCase(TestCase):
    def setUp(self):
        # 1. Alicuota, Categoria y Zonas
        self.alicuota = AlicuotaIVA.objects.create(descripcion='21%', porcentaje=Decimal('21.00'))
        self.categoria = Categoria.objects.create(nombre='Bebidas', activo=True)
        self.zona_norte = Zona.objects.create(nombre='Zona Norte')
        self.zona_sur = Zona.objects.create(nombre='Zona Sur')
        self.condicion_iva = CondicionIVA.objects.create(codigo='RI', descripcion='Responsable Inscripto', discrimina_iva=True)

        # 2. Productos
        self.prod1 = Producto.objects.create(
            codigo='BEB01',
            nombre='Gaseosa Cola 2.25L',
            costo=Decimal('1000.00'),
            stock_actual=Decimal('100.00'),
            categoria=self.categoria,
            alicuota_iva=self.alicuota,
            activo=True
        )

        self.presentacion_pack = Presentacion.objects.create(
            producto=self.prod1,
            nombre='Pack x6',
            factor_unidades=Decimal('6.00'),
            es_default=False
        )

        # 3. Lista de Precios
        self.lista_precio = ListaPrecio.objects.create(nombre='Mayorista General', activa=True)
        self.precio_prod1 = PrecioProducto.objects.create(
            lista=self.lista_precio,
            producto=self.prod1,
            precio_neto=Decimal('1000.00'),
            precio_final=Decimal('1210.00')
        )

        # 4. Vendedor
        self.user_vendedor = Usuario.objects.create_user(
            username='vendedor',
            email='vendedor@jcdistribuciones.com',
            password='password123',
            nombre_completo='Carlos Vendedor',
            rol='VENDEDOR'
        )
        self.vendedor = Vendedor.objects.create(
            usuario=self.user_vendedor,
            nombre='Carlos',
            apellido='Vendedor',
            comision_porcentaje=Decimal('5.00'), # 5% de comisión
            activo=True
        )

        # 5. Clientes (Cliente A en Zona Norte Día 1-Lunes, Cliente B en Zona Sur Día 2-Martes)
        self.user_cliente_a = Usuario.objects.create_user(
            username='cliente_a',
            email='clientea@test.com',
            password='password123',
            cuit='30111111119',
            nombre_completo='Cliente A SRL',
            rol='CLIENTE'
        )
        self.cliente_a = Cliente.objects.create(
            usuario=self.user_cliente_a,
            razon_social='Cliente A SRL',
            cuit='30111111119',
            condicion_iva=self.condicion_iva,
            zona=self.zona_norte,
            dia_reparto=1, # Lunes
            vendedor=self.vendedor,
            lista_precio_default=self.lista_precio,
            estado='ACTIVO'
        )

        self.user_cliente_b = Usuario.objects.create_user(
            username='cliente_b',
            email='clienteb@test.com',
            password='password123',
            cuit='30222222229',
            nombre_completo='Cliente B SRL',
            rol='CLIENTE'
        )
        self.cliente_b = Cliente.objects.create(
            usuario=self.user_cliente_b,
            razon_social='Cliente B SRL',
            cuit='30222222229',
            condicion_iva=self.condicion_iva,
            zona=self.zona_sur,
            dia_reparto=2, # Martes
            vendedor=self.vendedor,
            lista_precio_default=self.lista_precio,
            estado='ACTIVO'
        )

        # Operador interno de Depósito
        self.user_deposito = Usuario.objects.create_user(
            username='deposito_user',
            email='deposito@jcdistribuciones.com',
            password='password123',
            nombre_completo='Operador Depósito',
            rol='DEPOSITO'
        )

        self.client = Client()

    def _crear_remito_para_cliente(self, cliente, cantidad_packs=2):
        pedido = PedidoService.crear_o_recuperar_borrador(cliente)
        PedidoService.agregar_item(pedido, self.prod1, self.presentacion_pack, cantidad=Decimal(str(cantidad_packs)))
        PedidoService.enviar_pedido(pedido)
        PedidoService.aprobar_pedido(pedido, self.user_vendedor)
        remito = ComprobanteService.emitir_remito_desde_pedido(pedido, usuario_emisor=self.user_vendedor)
        return remito

    def test_generar_planilla_carga_consolidada(self):
        remito1 = self._crear_remito_para_cliente(self.cliente_a, cantidad_packs=3)
        remito2 = self._crear_remito_para_cliente(self.cliente_b, cantidad_packs=2)

        remitos_qs = LogisticaService.obtener_remitos_para_reparto()
        self.assertEqual(remitos_qs.count(), 2)

        planilla = LogisticaService.generar_planilla_carga(remitos_qs)
        self.assertEqual(len(planilla), 1)

        item_consolidado = planilla[0]
        self.assertEqual(item_consolidado['codigo'], 'BEB01')
        self.assertEqual(item_consolidado['cantidad'], Decimal('5.00')) # 3 + 2 = 5 packs
        self.assertEqual(item_consolidado['unidades_base'], Decimal('30.00')) # 5 * 6 = 30 unidades base

    def test_filtro_hoja_ruta_por_zona_y_dia(self):
        remito1 = self._crear_remito_para_cliente(self.cliente_a, cantidad_packs=1)
        remito2 = self._crear_remito_para_cliente(self.cliente_b, cantidad_packs=1)

        # Filtrar por Zona Norte
        remitos_norte = LogisticaService.obtener_remitos_para_reparto(zona_id=self.zona_norte.id)
        self.assertEqual(remitos_norte.count(), 1)
        self.assertEqual(remitos_norte.first(), remito1)

        # Filtrar por Día Martes (dia_semana=2)
        remitos_martes = LogisticaService.obtener_remitos_para_reparto(dia_semana=2)
        self.assertEqual(remitos_martes.count(), 1)
        self.assertEqual(remitos_martes.first(), remito2)

    def test_reporte_ventas_comisiones(self):
        remito1 = self._crear_remito_para_cliente(self.cliente_a, cantidad_packs=2)

        resumen = LogisticaService.obtener_resumen_ventas_vendedor()
        self.assertEqual(len(resumen), 1)

        info_vendedor = resumen[0]
        self.assertEqual(info_vendedor['vendedor'], self.vendedor)
        self.assertEqual(info_vendedor['cant_comprobantes'], 1)
        self.assertEqual(info_vendedor['total_facturado'], remito1.monto_total)
        
        # Comisión esperada = monto_total * 5%
        comision_esperada = remito1.monto_total * Decimal('0.05')
        self.assertEqual(info_vendedor['comision_estimada'], comision_esperada.quantize(Decimal('0.01')))

    def test_permisos_reportes(self):
        # Cliente intenta acceder a la hoja de ruta -> 403 Forbidden
        self.client.login(username='cliente_a', password='password123')
        response = self.client.get(reverse('reportes:hoja_ruta'))
        self.assertEqual(response.status_code, 403)

        # Operador de Depósito accede -> 200 OK
        self.client.login(username='deposito_user', password='password123')
        response = self.client.get(reverse('reportes:hoja_ruta'))
        self.assertEqual(response.status_code, 200)
