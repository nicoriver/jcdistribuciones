from decimal import Decimal
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from usuarios.models import Usuario
from proveedores.models import Proveedor
from productos.models import Categoria, Marca, Producto, TipoListaPrecio, PrecioProducto
from stock.models import MovimientoStock
from compras.models import Compra, DetalleCompra
from compras.services import CompraService


class ComprasServiceTestCase(TestCase):
    def setUp(self):
        # 1. Usuario operador
        self.supervisor = Usuario.objects.create_user(
            username='sup_compras',
            cuit_dni='20999888771',
            email='sup@jcdistribuciones.com',
            password='Password123!',
            rol='SUPERVISOR',
            is_staff=True
        )

        # 2. Proveedor
        self.proveedor = Proveedor.objects.create(
            cuit='30554433221',
            razon_social='Arcor SA Distribución Mayorista',
            domicilio='Ruta Nacional 12 Km 10',
            telefono='0376-4445555',
            email='ventas@arcor.com.ar',
            activo=True
        )

        # 3. Categoría y Marca
        self.cat = Categoria.objects.create(nombre='Almacén', activa=True)
        self.marca = Marca.objects.create(nombre='Arcor', activa=True)

        # 4. Productos de prueba
        # Prod 1: Controla stock, costo inicial 2000.00, stock inicial 10
        self.prod1 = Producto.objects.create(
            codigo='PROD-CMP-01',
            nombre='Mermelada Arcor Frutilla 454g',
            categoria=self.cat,
            marca=self.marca,
            proveedor_habitual=self.proveedor,
            alicuota_iva=Decimal('21.00'),
            costo_base=Decimal('2000.00'),
            stock_actual=10,
            controla_stock=True,
            activo=True
        )

        # Prod 2: NO controla stock, costo inicial 1500.00, stock 0
        self.prod2 = Producto.objects.create(
            codigo='PROD-CMP-02',
            nombre='Servicio Flete Especial',
            categoria=self.cat,
            marca=self.marca,
            alicuota_iva=Decimal('21.00'),
            costo_base=Decimal('1500.00'),
            stock_actual=0,
            controla_stock=False,
            activo=True
        )

        # 5. Listas de Precios
        self.lista_mayorista = TipoListaPrecio.objects.create(
            nombre='Mayorista',
            descripcion='Lista para comercios',
            activa=True
        )
        self.lista_distribuidor = TipoListaPrecio.objects.create(
            nombre='Distribuidor',
            descripcion='Lista para distribuidores zonales',
            activa=True
        )

        # Precios iniciales para Prod 1:
        # Mayorista: Recargo 40%, Descuento 10%
        # Con costo 2000: Neto = 2000 * 1.40 = 2800.00; Final = 2800 * 1.21 * 0.90 = 3049.20
        self.precio_may_prod1 = PrecioProducto.objects.create(
            producto=self.prod1,
            tipo_lista=self.lista_mayorista,
            porcentaje_recargo=Decimal('40.00'),
            porcentaje_descuento=Decimal('10.00')
        )
        self.precio_may_prod1.calcular_y_guardar(save=True)

        # Distribuidor: Recargo 25%, Descuento 5%
        # Con costo 2000: Neto = 2000 * 1.25 = 2500.00; Final = 2500 * 1.21 * 0.95 = 2873.75
        self.precio_dist_prod1 = PrecioProducto.objects.create(
            producto=self.prod1,
            tipo_lista=self.lista_distribuidor,
            porcentaje_recargo=Decimal('25.00'),
            porcentaje_descuento=Decimal('5.00')
        )
        self.precio_dist_prod1.calcular_y_guardar(save=True)

    def test_registro_compra_exitoso_y_actualizaciones(self):
        """
        Prueba a, b, c, d:
        - Registro exitoso de compra con múltiples ítems.
        - Incremento de stock_actual y creación de MovimientoStock con saldos exactos.
        - Actualización del costo_base al nuevo valor comprado.
        - Recálculo automático de listas de precios según fórmula canónica.
        """
        nuevo_costo_prod1 = Decimal('2500.00') # Mismo costo del caso testigo canónico
        cantidad_prod1 = 20
        cantidad_prod2 = 5
        nuevo_costo_prod2 = Decimal('1800.00')

        items = [
            {
                'producto': self.prod1,
                'cantidad': cantidad_prod1,
                'precio_costo_unitario': nuevo_costo_prod1
            },
            {
                'producto': self.prod2,
                'cantidad': cantidad_prod2,
                'precio_costo_unitario': nuevo_costo_prod2
            }
        ]

        compra = CompraService.registrar_compra(
            proveedor=self.proveedor,
            usuario=self.supervisor,
            nro_comprobante="FC-0001-00004567",
            items=items,
            observaciones="Compra de reposición mensual"
        )

        # 1. Verificación de Compra y Detalles
        self.assertIsNotNone(compra.id)
        self.assertEqual(compra.detalles.count(), 2)
        total_esperado = (nuevo_costo_prod1 * cantidad_prod1) + (nuevo_costo_prod2 * cantidad_prod2)
        # 2500 * 20 = 50.000 + 1800 * 5 = 9.000 -> 59.000.00
        self.assertEqual(compra.total_compra, Decimal('59000.00'))

        # 2. Verificación de Prod 1 (controla stock = True)
        self.prod1.refresh_from_db()
        self.assertEqual(self.prod1.stock_actual, 30) # 10 anterior + 20
        self.assertEqual(self.prod1.costo_base, nuevo_costo_prod1)

        # 3. Verificación de Kardex MovimientoStock para Prod 1
        mov1 = MovimientoStock.objects.filter(
            producto=self.prod1,
            documento_referencia=f"Compra {compra.nro_comprobante_proveedor}"
        ).first()
        self.assertIsNotNone(mov1)
        self.assertEqual(mov1.tipo_movimiento, 'ENTRADA_COMPRA')
        self.assertEqual(mov1.cantidad, 20)
        self.assertEqual(mov1.stock_anterior, 10)
        self.assertEqual(mov1.stock_resultante, 30)
        self.assertEqual(mov1.usuario, self.supervisor)

        # 4. Verificación de Prod 2 (controla stock = False)
        self.prod2.refresh_from_db()
        self.assertEqual(self.prod2.stock_actual, 0) # No se modifica al no controlar stock
        self.assertEqual(self.prod2.costo_base, nuevo_costo_prod2)

        # 5. Verificación de recálculo en Listas de Precios de Prod 1:
        # Costo: 2500, Recargo Mayorista 40%, IVA 21%, Descuento 10%:
        # P_recargo = 2500 * 1.40 = 3500.00
        # P_final   = 3500 * 1.21 * 0.90 = 3811.50 (Caso testigo canónico!)
        self.precio_may_prod1.refresh_from_db()
        self.assertEqual(self.precio_may_prod1.precio_neto, Decimal('3500.00'))
        self.assertEqual(self.precio_may_prod1.precio_final, Decimal('3811.50'))

        # Distribuidor: Costo 2500, Recargo 25%, IVA 21%, Descuento 5%:
        # P_recargo = 2500 * 1.25 = 3125.00
        # P_iva     = 3125 * 1.21 = 3781.25
        # P_final   = 3781.25 * 0.95 = 3592.1875 -> 3592.19
        self.precio_dist_prod1.refresh_from_db()
        self.assertEqual(self.precio_dist_prod1.precio_neto, Decimal('3125.00'))
        self.assertEqual(self.precio_dist_prod1.precio_final, Decimal('3592.19'))

    def test_rollback_atomico_ante_error(self):
        """
        Prueba e:
        Manejo de rollback atómico: Si un ítem falla en la compra (ej. costo negativo o cantidad <= 0),
        ningún registro debe quedar persistido (ni Compra, ni Stock, ni cambios en precios).
        """
        stock_original = self.prod1.stock_actual
        costo_original = self.prod1.costo_base

        items_invalidos = [
            {
                'producto': self.prod1,
                'cantidad': 15,
                'precio_costo_unitario': Decimal('3000.00')
            },
            {
                'producto': self.prod2,
                'cantidad': -2, # Inválido!
                'precio_costo_unitario': Decimal('1000.00')
            }
        ]

        with self.assertRaises(ValidationError):
            CompraService.registrar_compra(
                proveedor=self.proveedor,
                usuario=self.supervisor,
                nro_comprobante="FC-FALLIDA-001",
                items=items_invalidos
            )

        # Verificar que nada se guardó
        self.assertEqual(Compra.objects.filter(nro_comprobante_proveedor="FC-FALLIDA-001").count(), 0)
        self.assertEqual(DetalleCompra.objects.count(), 0)
        self.assertEqual(MovimientoStock.objects.filter(documento_referencia="Compra FC-FALLIDA-001").count(), 0)

        # Los productos deben conservar sus valores originales intactos
        self.prod1.refresh_from_db()
        self.assertEqual(self.prod1.stock_actual, stock_original)
        self.assertEqual(self.prod1.costo_base, costo_original)
