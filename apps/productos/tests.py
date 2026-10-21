from decimal import Decimal
from django.test import TestCase
from django.db import IntegrityError
from django.db.models import ProtectedError
from productos.models import Categoria, Marca, Producto, Presentacion, TipoListaPrecio, PrecioProducto
from productos.services import CalculadoraPreciosService
from proveedores.models import Proveedor
from clientes.models import Cliente, Vendedor
from geografia.models import Zona


class Modulo3CatalogoPreciosTestCase(TestCase):
    def setUp(self):
        # 1. Categoría, Marca y Proveedor
        self.categoria = Categoria.objects.create(nombre="Almacén", descripcion="Comestibles secos", activa=True)
        self.marca = Marca.objects.create(nombre="Arcor", activa=True)
        self.proveedor = Proveedor.objects.create(cuit="30-11223344-5", razon_social="Arcor SAIC")

        # 2. Producto base
        self.producto = Producto.objects.create(
            codigo="GAL-001",
            codigo_barras="7791234567890",
            nombre="Galletitas Maná Vainilla 150g",
            descripcion="Galletitas dulces sabor vainilla",
            categoria=self.categoria,
            marca=self.marca,
            proveedor_habitual=self.proveedor,
            alicuota_iva=Decimal('21.00'),
            costo_base=Decimal('2500.00'),
            stock_actual=100,
            punto_reposicion=20,
            controla_stock=True,
            activo=True
        )

        # 3. Presentaciones
        self.pres_unidad = Presentacion.objects.create(
            producto=self.producto,
            nombre="Unidad",
            factor_conversion=1,
            es_default=True
        )
        self.pres_pack = Presentacion.objects.create(
            producto=self.producto,
            nombre="Pack x6",
            factor_conversion=6,
            es_default=False
        )

        # 4. Tipo de Lista de Precios
        self.lista_mayorista = TipoListaPrecio.objects.create(
            nombre="Mayorista General",
            descripcion="Lista para comercios y autoservicios",
            activa=True
        )

    def test_algoritmo_calculo_precios_caso_testigo(self):
        """
        a) Verifica el algoritmo canónico con el caso testigo:
        Costo 2500, Recargo 40%, IVA 21%, Descuento 10% -> Precio Final = 3811.50.
        P_recargo = 2500 * 1.40 = 3500.00
        P_iva = 3500 * 1.21 = 4235.00
        P_final = 4235 * (1 - 0.10) = 3811.50
        """
        precio_final = CalculadoraPreciosService.calcular_precio_final(
            costo=Decimal('2500.00'),
            recargo_porc=Decimal('40.00'),
            iva_porc=Decimal('21.00'),
            descuento_porc=Decimal('10.00')
        )
        self.assertEqual(precio_final, Decimal('3811.50'))

    def test_almacenamiento_precision_sin_overflow_cifras_grandes(self):
        """
        b) Verifica que campos DecimalField(14,2) soporten montos reales de inflación
        superiores a $10.000 y $10.000.000 sin desbordamiento numérico.
        """
        producto_caro = Producto.objects.create(
            codigo="MAQ-999",
            nombre="Cámara Frigorífica Industrial",
            categoria=self.categoria,
            costo_base=Decimal('25450890.75'),  # Más de 25 millones de pesos
            alicuota_iva=Decimal('21.00')
        )

        precio_caro = PrecioProducto.objects.create(
            producto=producto_caro,
            tipo_lista=self.lista_mayorista,
            porcentaje_recargo=Decimal('25.50'),
            porcentaje_descuento=Decimal('5.00')
        )

        precio_caro.calcular_y_guardar()
        precio_caro.refresh_from_db()

        # Verificar que el precio neto y precio final se persistan exactamente sin truncamiento
        # P_recargo = 25450890.75 * 1.255 = 31940867.89125 -> 31940867.89
        self.assertEqual(precio_caro.precio_neto, Decimal('31940867.89'))
        self.assertTrue(precio_caro.precio_final > Decimal('35000000.00'))

    def test_recalculo_automatico_precios_al_actualizar_costo_base(self):
        """
        c) Verifica que CalculadoraPreciosService.actualizar_precios_producto(producto)
        recalcule automáticamente precios netos y finales al modificarse el costo base.
        """
        precio = PrecioProducto.objects.create(
            producto=self.producto,
            tipo_lista=self.lista_mayorista,
            porcentaje_recargo=Decimal('40.00'),
            porcentaje_descuento=Decimal('10.00')
        )
        precio.calcular_y_guardar()
        self.assertEqual(precio.precio_final, Decimal('3811.50'))
        self.assertEqual(precio.precio_neto, Decimal('3500.00'))

        # Actualizar costo base de 2500 a 5000 (aumento del 100%)
        self.producto.costo_base = Decimal('5000.00')
        self.producto.save(update_fields=['costo_base'])

        # Invocar servicio de recálculo masivo
        actualizados = CalculadoraPreciosService.actualizar_precios_producto(self.producto)
        self.assertEqual(actualizados, 1)

        precio.refresh_from_db()
        # Nuevo precio neto: 5000 * 1.40 = 7000.00
        self.assertEqual(precio.precio_neto, Decimal('7000.00'))
        # Nuevo precio final: 3811.50 * 2 = 7623.00
        self.assertEqual(precio.precio_final, Decimal('7623.00'))

    def test_integridad_referencial_tipolistaprecio_en_cliente(self):
        """
        d) Verifica la integridad referencial y protección ante borrado
        de TipoListaPrecio asignado a un Cliente (PROTECT).
        """
        zona = Zona.objects.create(nombre="Zona Centro", activa=True)
        vendedor = Vendedor.objects.create(legajo="VEND-100", nombre="Vendedor Test", activo=True)

        cliente = Cliente.objects.create(
            cuit="30999999991",
            razon_social="Cliente Test SRL",
            domicilio="Calle 1",
            zona=zona,
            vendedor=vendedor,
            tipo_lista_precio=self.lista_mayorista
        )

        self.assertEqual(cliente.tipo_lista_precio, self.lista_mayorista)
        self.assertEqual(cliente.lista_precio_default, self.lista_mayorista)

        # Intentar borrar TipoListaPrecio asignada a un cliente debe arrojar ProtectedError
        with self.assertRaises(ProtectedError):
            self.lista_mayorista.delete()
