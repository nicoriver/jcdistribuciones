from decimal import Decimal
from django.db import models, transaction


class PuntoVentaNumerador(models.Model):
    TIPOS_DOCUMENTO = [
        ('REMITO', 'Remito Comercial A4'),
        ('NC', 'Nota de Crédito por Devolución'),
        ('NCF', 'Nota de Crédito por Faltante'),
    ]

    punto_venta = models.PositiveIntegerField(
        default=1,
        verbose_name="Punto de Venta"
    )
    tipo_documento = models.CharField(
        max_length=20,
        choices=TIPOS_DOCUMENTO,
        verbose_name="Tipo de Documento"
    )
    ultimo_numero = models.PositiveIntegerField(
        default=0,
        verbose_name="Último Número Emitido"
    )

    class Meta:
        verbose_name = "Numerador de Punto de Venta"
        verbose_name_plural = "Numeradores de Puntos de Venta"
        unique_together = ('punto_venta', 'tipo_documento')
        ordering = ['punto_venta', 'tipo_documento']

    def __str__(self):
        return f"PV {self.punto_venta:04d} - {self.get_tipo_documento_display()} (Último: {self.ultimo_numero:08d})"


class Remito(models.Model):
    ESTADOS = [
        ('EMITIDO', 'Emitido'),
        ('ENTREGADO', 'Entregado'),
        ('ANULADO', 'Anulado'),
    ]

    punto_venta = models.PositiveIntegerField(
        default=1,
        verbose_name="Punto de Venta"
    )
    numero = models.PositiveIntegerField(
        default=1,
        verbose_name="Número Correlativo"
    )
    numero_completo = models.CharField(
        max_length=30,
        unique=True,
        db_index=True,
        verbose_name="Número Completo de Remito"
    )
    cliente = models.ForeignKey(
        'clientes.Cliente',
        on_delete=models.PROTECT,
        related_name='remitos',
        verbose_name="Cliente"
    )
    vendedor = models.ForeignKey(
        'clientes.Vendedor',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='remitos',
        verbose_name="Vendedor"
    )
    supervisor = models.ForeignKey(
        'usuarios.Usuario',
        on_delete=models.PROTECT,
        related_name='remitos_emitidos',
        verbose_name="Supervisor / Emisor"
    )
    pedido = models.ForeignKey(
        'pedidos.Pedido',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='remitos',
        verbose_name="Pedido Origen (FK)"
    )
    pedido_origen_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="ID Pedido de Origen"
    )
    fecha = models.DateField(
        null=True,
        blank=True,
        verbose_name="Fecha Comercial",
        help_text="Fecha comercial elegida para el comprobante"
    )
    tipo_lista_precio = models.ForeignKey(
        'productos.TipoListaPrecio',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='remitos',
        verbose_name="Lista de Precios Utilizada"
    )
    fecha_emision = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de Emisión"
    )
    subtotal_bruto = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Subtotal Bruto"
    )
    total_descuento = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Total Descuento"
    )
    monto_total = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Monto Total Comercial"
    )
    observaciones = models.TextField(
        blank=True,
        default='',
        verbose_name="Observaciones"
    )
    anulado = models.BooleanField(
        default=False,
        verbose_name="Anulado"
    )
    estado = models.CharField(
        max_length=20,
        choices=ESTADOS,
        default='EMITIDO',
        verbose_name="Estado del Remito"
    )

    class Meta:
        verbose_name = "Remito Comercial"
        verbose_name_plural = "Remitos Comerciales"
        ordering = ['-fecha_emision']

    def __str__(self):
        return f"{self.numero_completo} - {self.cliente.razon_social}"

    def __init__(self, *args, **kwargs):
        if 'numero_remito' in kwargs and 'numero_completo' not in kwargs:
            kwargs['numero_completo'] = kwargs.pop('numero_remito')
        if 'emitido_por' in kwargs and 'supervisor' not in kwargs:
            kwargs['supervisor'] = kwargs.pop('emitido_por')
        super().__init__(*args, **kwargs)

    def save(self, *args, **kwargs):
        if self.pedido_id and not self.pedido_origen_id:
            self.pedido_origen_id = self.pedido_id
        if self.anulado and self.estado != 'ANULADO':
            self.estado = 'ANULADO'
        elif not self.anulado and self.estado == 'ANULADO':
            self.estado = 'EMITIDO'
        super().save(*args, **kwargs)

    # Propiedades de compatibilidad
    @property
    def fecha_comercial(self):
        if self.fecha:
            return self.fecha
        if self.fecha_emision:
            from django.utils import timezone
            return timezone.localtime(self.fecha_emision).date()
        return None

    @property
    def numero_remito(self):
        return self.numero_completo

    @numero_remito.setter
    def numero_remito(self, value):
        self.numero_completo = value

    @property
    def emitido_por(self):
        return self.supervisor

    @emitido_por.setter
    def emitido_por(self, value):
        self.supervisor = value

    @property
    def items(self):
        return self.detalles

    @property
    def total_comercial(self):
        return self.monto_total

    @classmethod
    def obtener_siguiente_numeracion(cls, punto_venta=1):
        """
        Obtiene e incrementa de forma transaccional y segura (select_for_update)
        el correlativo en PuntoVentaNumerador para el tipo REMITO.
        Retorna (numero, numero_completo).
        """
        numerador, _ = PuntoVentaNumerador.objects.select_for_update().get_or_create(
            punto_venta=punto_venta,
            tipo_documento='REMITO',
            defaults={'ultimo_numero': 0}
        )
        numerador.ultimo_numero += 1
        numerador.save(update_fields=['ultimo_numero'])
        numero = numerador.ultimo_numero
        numero_completo = f"R-{punto_venta:04d}-{numero:08d}"
        return numero, numero_completo

    @classmethod
    def generar_siguiente_numero(cls, punto_venta=1):
        _, numero_completo = cls.obtener_siguiente_numeracion(punto_venta=punto_venta)
        return numero_completo


class DetalleRemito(models.Model):
    remito = models.ForeignKey(
        Remito,
        on_delete=models.CASCADE,
        related_name='detalles',
        verbose_name="Remito"
    )
    detalle_pedido_origen = models.ForeignKey(
        'pedidos.DetallePedido',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name="Renglón Pedido Origen"
    )
    producto = models.ForeignKey(
        'productos.Producto',
        on_delete=models.PROTECT,
        verbose_name="Producto"
    )
    presentacion = models.ForeignKey(
        'productos.Presentacion',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Presentación"
    )
    presentacion_nombre = models.CharField(
        max_length=50,
        blank=True,
        default='',
        verbose_name="Nombre de Presentación"
    )
    factor_unidades = models.IntegerField(
        default=1,
        verbose_name="Factor Unidades"
    )
    codigo_historico = models.CharField(
        max_length=50,
        verbose_name="Código Histórico"
    )
    descripcion_historica = models.CharField(
        max_length=150,
        verbose_name="Descripción Histórica"
    )
    cantidad = models.IntegerField(
        verbose_name="Cantidad"
    )
    precio_unitario_historico = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        verbose_name="Precio Unitario Histórico"
    )
    porcentaje_descuento = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="% Descuento"
    )
    subtotal = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        verbose_name="Subtotal"
    )
    cantidad_devuelta = models.IntegerField(
        default=0,
        verbose_name="Cantidad Devuelta / Faltante"
    )

    class Meta:
        verbose_name = "Detalle de Remito"
        verbose_name_plural = "Detalles de Remitos"

    def __str__(self):
        return f"{self.codigo_historico} - {self.descripcion_historica} x {self.cantidad}"

    def __init__(self, *args, **kwargs):
        if 'precio_unitario' in kwargs and 'precio_unitario_historico' not in kwargs:
            kwargs['precio_unitario_historico'] = kwargs.pop('precio_unitario')
        if 'descuento_porcentaje' in kwargs and 'porcentaje_descuento' not in kwargs:
            kwargs['porcentaje_descuento'] = kwargs.pop('descuento_porcentaje')
        if 'total_linea' in kwargs and 'subtotal' not in kwargs:
            kwargs['subtotal'] = kwargs.pop('total_linea')
        super().__init__(*args, **kwargs)

    def save(self, *args, **kwargs):
        if self.presentacion and not self.presentacion_nombre:
            self.presentacion_nombre = self.presentacion.nombre
        super().save(*args, **kwargs)

    # Propiedades de compatibilidad
    @property
    def precio_unitario(self):
        return self.precio_unitario_historico

    @precio_unitario.setter
    def precio_unitario(self, value):
        self.precio_unitario_historico = value

    @property
    def descuento_porcentaje(self):
        return self.porcentaje_descuento

    @descuento_porcentaje.setter
    def descuento_porcentaje(self, value):
        self.porcentaje_descuento = value

    @property
    def total_linea(self):
        return self.subtotal

    @total_linea.setter
    def total_linea(self, value):
        self.subtotal = value

    @property
    def saldo_devolvible(self):
        return self.cantidad - self.cantidad_devuelta


class NotaCreditoInterna(models.Model):
    MOTIVOS = [
        ('NCF', 'Faltante de Carga / Despacho'),
        ('NC', 'Devolución posterior de mercadería'),
    ]

    punto_venta = models.PositiveIntegerField(
        default=1,
        verbose_name="Punto de Venta"
    )
    numero = models.PositiveIntegerField(
        default=1,
        verbose_name="Número Correlativo"
    )
    numero_nc = models.CharField(
        max_length=30,
        unique=True,
        editable=False,
        verbose_name="Número Nota de Crédito"
    )
    remito = models.ForeignKey(
        Remito,
        on_delete=models.PROTECT,
        related_name='notas_credito',
        verbose_name="Remito de Origen"
    )
    motivo_tipo = models.CharField(
        max_length=10,
        choices=MOTIVOS,
        verbose_name="Tipo de Motivo"
    )
    fecha = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha y Hora"
    )
    reingresa_stock = models.BooleanField(
        default=False,
        verbose_name="Reingresa a Stock",
        help_text="Decisión del supervisor/depósito si la mercadería vuelve a stock"
    )
    monto_total = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Monto Total NC"
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

    class Meta:
        verbose_name = "Nota de Crédito Interna"
        verbose_name_plural = "Notas de Crédito Internas"
        ordering = ['-fecha']

    def __str__(self):
        return f"{self.numero_nc} ({self.get_motivo_tipo_display()}) - Remito {self.remito.numero_completo}"

    @classmethod
    def obtener_siguiente_numeracion(cls, tipo_documento='NC', punto_venta=1):
        tipo_doc = tipo_documento if tipo_documento in ['NC', 'NCF'] else 'NC'
        numerador, _ = PuntoVentaNumerador.objects.select_for_update().get_or_create(
            punto_venta=punto_venta,
            tipo_documento=tipo_doc,
            defaults={'ultimo_numero': 0}
        )
        numerador.ultimo_numero += 1
        numerador.save(update_fields=['ultimo_numero'])
        numero = numerador.ultimo_numero
        numero_nc = f"{tipo_doc}-{punto_venta:04d}-{numero:08d}"
        return numero, numero_nc

    @classmethod
    def generar_siguiente_numero(cls, tipo_documento='NC', punto_venta=1):
        _, numero_nc = cls.obtener_siguiente_numeracion(tipo_documento=tipo_documento, punto_venta=punto_venta)
        return numero_nc


class DetalleNotaCredito(models.Model):
    nota_credito = models.ForeignKey(
        NotaCreditoInterna,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name="Nota de Crédito"
    )
    detalle_remito = models.ForeignKey(
        DetalleRemito,
        on_delete=models.PROTECT,
        related_name='devoluciones',
        verbose_name="Renglón de Remito Origen"
    )
    cantidad = models.IntegerField(
        verbose_name="Cantidad Devuelta"
    )
    precio_unitario = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        verbose_name="Precio Unitario"
    )
    total_linea = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        verbose_name="Total Línea"
    )

    class Meta:
        verbose_name = "Renglón de Nota de Crédito"
        verbose_name_plural = "Renglones de Notas de Crédito"

    def __str__(self):
        return f"{self.detalle_remito.descripcion_historica} x {self.cantidad}"
