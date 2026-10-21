from decimal import Decimal
from django.db import models


class Compra(models.Model):
    proveedor = models.ForeignKey(
        'proveedores.Proveedor',
        on_delete=models.PROTECT,
        related_name='compras',
        verbose_name="Proveedor"
    )
    usuario = models.ForeignKey(
        'usuarios.Usuario',
        on_delete=models.PROTECT,
        related_name='compras_registradas',
        verbose_name="Usuario Operador"
    )
    nro_comprobante_proveedor = models.CharField(
        max_length=50,
        verbose_name="Nro. Comprobante Proveedor",
        help_text="Ej: Factura o Remito del proveedor (FC-0001-00004567)"
    )
    fecha_emision = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha y Hora de Registro"
    )
    total_compra = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Total de la Compra"
    )
    observaciones = models.TextField(
        blank=True,
        default='',
        verbose_name="Observaciones"
    )

    class Meta:
        verbose_name = "Compra"
        verbose_name_plural = "Compras"
        ordering = ['-fecha_emision']

    def __str__(self):
        return f"Compra #{self.id} - {self.nro_comprobante_proveedor} ({self.proveedor.razon_social})"


class DetalleCompra(models.Model):
    compra = models.ForeignKey(
        Compra,
        on_delete=models.CASCADE,
        related_name='detalles',
        verbose_name="Compra"
    )
    producto = models.ForeignKey(
        'productos.Producto',
        on_delete=models.PROTECT,
        related_name='detalles_compras',
        verbose_name="Producto"
    )
    cantidad = models.IntegerField(
        verbose_name="Cantidad Comprada",
        help_text="Cantidad de unidades base ingresadas"
    )
    precio_costo_unitario = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        verbose_name="Precio de Costo Unitario"
    )
    subtotal = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        verbose_name="Subtotal"
    )

    class Meta:
        verbose_name = "Detalle de Compra"
        verbose_name_plural = "Detalles de Compras"

    def __str__(self):
        return f"{self.producto.nombre} x {self.cantidad} a ${self.precio_costo_unitario}"
