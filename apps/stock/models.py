from django.db import models


class ConfiguracionStock(models.Model):
    control_stock_habilitado = models.BooleanField(
        default=True,
        verbose_name="Control General de Stock Habilitado",
        help_text="Flag general para activar o pausar el descuento de stock"
    )
    permitir_stock_negativo_con_alerta = models.BooleanField(
        default=True,
        verbose_name="Permitir Stock Negativo con Alerta"
    )

    class Meta:
        verbose_name = "Configuración de Stock"
        verbose_name_plural = "Configuraciones de Stock"

    def __str__(self):
        estado = "Habilitado" if self.control_stock_habilitado else "Pausado"
        return f"Configuración de Stock ({estado})"

    @classmethod
    def get_solo(cls):
        config, _ = cls.objects.get_or_create(id=1)
        return config


class MovimientoStock(models.Model):
    TIPOS_MOVIMIENTO = [
        ('ENTRADA_COMPRA', 'Entrada por Compra'),
        ('INGRESO_COMPRA', 'Ingreso por Compra (Legacy)'),
        ('SALIDA_VENTA', 'Salida por Venta'),
        ('SALIDA_REMITO', 'Salida por Remito (Venta)'),
        ('DEVOLUCION_NC', 'Devolución Nota de Crédito'),
        ('AJUSTE_POSITIVO', 'Ajuste de Stock Positivo'),
        ('AJUSTE_NEGATIVO', 'Ajuste de Stock Negativo'),
        ('AJUSTE_INVENTARIO', 'Ajuste Manual'),
        ('ANULACION', 'Anulación de Documento'),
    ]

    producto = models.ForeignKey(
        'productos.Producto',
        on_delete=models.PROTECT,
        related_name='movimientos_stock',
        verbose_name="Producto"
    )
    tipo_movimiento = models.CharField(
        max_length=30,
        choices=TIPOS_MOVIMIENTO,
        verbose_name="Tipo de Movimiento"
    )
    cantidad = models.IntegerField(
        verbose_name="Cantidad",
        help_text="Positivo para ingresos, negativo para egresos"
    )
    stock_anterior = models.IntegerField(
        verbose_name="Stock Anterior"
    )
    stock_resultante = models.IntegerField(
        verbose_name="Stock Resultante"
    )
    documento_referencia = models.CharField(
        max_length=100,
        blank=True,
        default='',
        verbose_name="Documento de Referencia",
        help_text="Ej: Factura Compra FC-0001-00004567 o REM-0001-00001234"
    )
    motivo = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name="Motivo / Observación"
    )
    observaciones = models.TextField(
        blank=True,
        default='',
        verbose_name="Observaciones"
    )
    usuario = models.ForeignKey(
        'usuarios.Usuario',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name="Usuario Operador"
    )
    fecha = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha y Hora"
    )

    class Meta:
        verbose_name = "Movimiento de Stock"
        verbose_name_plural = "Libro de Movimientos de Stock"
        ordering = ['-fecha']

    def __str__(self):
        return f"[{self.fecha.strftime('%Y-%m-%d %H:%M')}] {self.get_tipo_movimiento_display()}: {self.producto.nombre} ({self.cantidad})"
