from decimal import Decimal, ROUND_HALF_UP
from django.db import models
from django.utils import timezone


class Pedido(models.Model):
    ESTADOS = [
        ('BORRADOR', 'Borrador'),
        ('PENDIENTE_REVISION', 'Pendiente de Revisión'),
        ('ENVIADO', 'Enviado por Cliente'),
        ('EN_REVISION', 'En Revisión'),
        ('APROBADO', 'Aprobado'),
        ('FACTURADO_REMITO', 'Facturado en Remito'),
        ('FACTURADO', 'Facturado (Legacy)'),
        ('RECHAZADO', 'Rechazado'),
    ]

    numero_pedido = models.CharField(
        max_length=25,
        unique=True,
        editable=False,
        db_index=True,
        verbose_name="Número de Pedido"
    )
    cliente = models.ForeignKey(
        'clientes.Cliente',
        on_delete=models.PROTECT,
        related_name='pedidos',
        verbose_name="Cliente"
    )
    vendedor = models.ForeignKey(
        'clientes.Vendedor',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pedidos',
        verbose_name="Vendedor Asignado"
    )
    lista_precio = models.ForeignKey(
        'productos.TipoListaPrecio',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='pedidos',
        verbose_name="Lista de Precios Aplicada"
    )
    fecha_creacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de Creación"
    )
    fecha_envio = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Fecha de Envío a Revisión"
    )
    estado = models.CharField(
        max_length=25,
        choices=ESTADOS,
        default='BORRADOR',
        db_index=True,
        verbose_name="Estado"
    )
    total_estimado = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Total Estimado Comercial"
    )
    monto_subtotal_neto = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Subtotal Neto Gravado"
    )
    monto_iva_total = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Total IVA"
    )
    observaciones = models.TextField(
        blank=True,
        default='',
        verbose_name="Observaciones"
    )
    motivo_rechazo = models.TextField(
        blank=True,
        default='',
        verbose_name="Motivo de Rechazo"
    )
    aprobado_por = models.ForeignKey(
        'usuarios.Usuario',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pedidos_aprobados',
        verbose_name="Aprobado por"
    )
    fecha_aprobacion = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Fecha de Aprobación"
    )
    remito_asociado_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="ID Remito Asociado"
    )

    class Meta:
        verbose_name = "Pedido de Venta"
        verbose_name_plural = "Pedidos de Venta"
        ordering = ['-fecha_creacion']

    def __str__(self):
        return f"{self.numero_pedido} - {self.cliente.razon_social} ({self.get_estado_display()})"

    def __init__(self, *args, **kwargs):
        if 'monto_total' in kwargs and 'total_estimado' not in kwargs:
            kwargs['total_estimado'] = kwargs.pop('monto_total')
        if 'observaciones_cliente' in kwargs and 'observaciones' not in kwargs:
            kwargs['observaciones'] = kwargs.pop('observaciones_cliente')
        super().__init__(*args, **kwargs)

    def save(self, *args, **kwargs):
        if not self.vendedor_id and self.cliente_id:
            self.vendedor = self.cliente.vendedor
        if not self.lista_precio_id and self.cliente_id:
            self.lista_precio = self.cliente.tipo_lista_precio
        if not self.numero_pedido:
            year = timezone.now().year
            last_pedido = Pedido.objects.filter(
                numero_pedido__startswith=f'PED-{year}-'
            ).order_by('id').last()

            if last_pedido and last_pedido.numero_pedido:
                try:
                    last_seq = int(last_pedido.numero_pedido.split('-')[-1])
                    new_seq = last_seq + 1
                except (ValueError, IndexError):
                    new_seq = 1
            else:
                new_seq = 1

            self.numero_pedido = f'PED-{year}-{new_seq:05d}'
        super().save(*args, **kwargs)

    # Propiedades de compatibilidad
    @property
    def monto_total(self):
        return self.total_estimado

    @monto_total.setter
    def monto_total(self, val):
        self.total_estimado = val

    @property
    def observaciones_cliente(self):
        return self.observaciones

    @observaciones_cliente.setter
    def observaciones_cliente(self, val):
        self.observaciones = val

    @property
    def items(self):
        return self.detalles

    def recalcular_totales(self, save=True):
        subtotal_neto = Decimal('0.00')
        iva_total = Decimal('0.00')
        total = Decimal('0.00')

        for item in self.detalles.all():
            subtotal_neto += (item.subtotal_neto or Decimal('0.00'))
            iva_total += (item.subtotal_iva or Decimal('0.00'))
            total += (item.subtotal or Decimal('0.00'))

        self.monto_subtotal_neto = subtotal_neto.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        self.monto_iva_total = iva_total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        self.total_estimado = total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        if save:
            self.save(update_fields=['monto_subtotal_neto', 'monto_iva_total', 'total_estimado'])
        return self.total_estimado


class DetallePedido(models.Model):
    pedido = models.ForeignKey(
        Pedido,
        on_delete=models.CASCADE,
        related_name='detalles',
        verbose_name="Pedido"
    )
    producto = models.ForeignKey(
        'productos.Producto',
        on_delete=models.PROTECT,
        related_name='detalles_pedido',
        verbose_name="Producto"
    )
    presentacion = models.ForeignKey(
        'productos.Presentacion',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Presentación Elegida"
    )
    factor_unidades = models.IntegerField(
        default=1,
        verbose_name="Factor Unidades Presentación"
    )
    cantidad = models.IntegerField(
        default=1,
        verbose_name="Cantidad Solicitada"
    )
    precio_unitario = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Precio Unitario Comercial"
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
        default=Decimal('0.00'),
        verbose_name="Subtotal Renglón"
    )

    # Campos de respaldo histórico y desglose impositivo interno
    unidades_totales = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Unidades Totales Base"
    )
    codigo_producto_historico = models.CharField(
        max_length=50,
        blank=True,
        default='',
        verbose_name="Código Histórico"
    )
    nombre_producto_historico = models.CharField(
        max_length=200,
        blank=True,
        default='',
        verbose_name="Nombre Histórico"
    )
    precio_unitario_neto = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Precio Unitario Neto (sin IVA)"
    )
    porcentaje_iva = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('21.00'),
        verbose_name="% IVA"
    )
    subtotal_neto = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Subtotal Neto"
    )
    subtotal_iva = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Subtotal IVA"
    )
    supera_stock_disponible = models.BooleanField(
        default=False,
        verbose_name="¿Supera Stock Disponible?"
    )

    class Meta:
        verbose_name = "Detalle de Pedido"
        verbose_name_plural = "Detalles de Pedidos"

    def __str__(self):
        nombre = self.nombre_producto_historico or (self.producto.nombre if self.producto_id else '')
        return f"{nombre} x {self.cantidad} ({self.pedido.numero_pedido})"

    def __init__(self, *args, **kwargs):
        if 'descuento_porcentaje' in kwargs and 'porcentaje_descuento' not in kwargs:
            kwargs['porcentaje_descuento'] = kwargs.pop('descuento_porcentaje')
        if 'total_linea' in kwargs and 'subtotal' not in kwargs:
            kwargs['subtotal'] = kwargs.pop('total_linea')
        super().__init__(*args, **kwargs)

    # Propiedades de compatibilidad
    @property
    def descuento_porcentaje(self):
        return self.porcentaje_descuento

    @descuento_porcentaje.setter
    def descuento_porcentaje(self, val):
        self.porcentaje_descuento = val

    @property
    def total_linea(self):
        return self.subtotal

    @total_linea.setter
    def total_linea(self, val):
        self.subtotal = val

    def calcular_linea(self, save=True):
        if self.presentacion_id and (not self.factor_unidades or self.factor_unidades == 1):
            self.factor_unidades = int(self.presentacion.factor_conversion or 1)
        factor = int(self.factor_unidades or 1)
        cant = int(Decimal(str(self.cantidad or 1)))
        self.cantidad = cant
        self.factor_unidades = factor
        self.unidades_totales = Decimal(cant * factor).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        if self.producto_id:
            if not self.codigo_producto_historico:
                self.codigo_producto_historico = self.producto.codigo
            if not self.nombre_producto_historico:
                self.nombre_producto_historico = self.producto.nombre

        desc_porc = Decimal(str(self.porcentaje_descuento or '0.00'))

        # Si se proveyó precio_unitario comercial directamente
        if self.precio_unitario and Decimal(str(self.precio_unitario)) > Decimal('0.00'):
            p_unit = Decimal(str(self.precio_unitario))
            bruto = p_unit * Decimal(cant)
            descuento = bruto * (desc_porc / Decimal('100.00'))
            self.subtotal = (bruto - descuento).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            if self.precio_unitario_neto and Decimal(str(self.precio_unitario_neto)) > Decimal('0.00'):
                precio_neto = Decimal(str(self.precio_unitario_neto))
                porc_iva = Decimal(str(self.porcentaje_iva or '21.00'))
                subtotal_bruto_neto = precio_neto * Decimal(cant)
                desc_neto = subtotal_bruto_neto * (desc_porc / Decimal('100.00'))
                self.subtotal_neto = (subtotal_bruto_neto - desc_neto).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                self.subtotal_iva = (self.subtotal_neto * (porc_iva / Decimal('100.00'))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            else:
                self.precio_unitario_neto = p_unit
                self.subtotal_neto = self.subtotal
        elif self.precio_unitario_neto and Decimal(str(self.precio_unitario_neto)) > Decimal('0.00'):
            precio_neto = Decimal(str(self.precio_unitario_neto))
            porc_iva = Decimal(str(self.porcentaje_iva or '21.00'))
            subtotal_bruto = precio_neto * Decimal(cant)
            descuento = subtotal_bruto * (desc_porc / Decimal('100.00'))
            self.subtotal_neto = (subtotal_bruto - descuento).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            self.subtotal_iva = (self.subtotal_neto * (porc_iva / Decimal('100.00'))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            self.subtotal = (self.subtotal_neto + self.subtotal_iva).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            self.precio_unitario = (precio_neto * (Decimal('1.00') + porc_iva / Decimal('100.00'))).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )

        if save:
            self.save()
        return self.subtotal

    def save(self, *args, **kwargs):
        if self.cantidad and (self.precio_unitario or self.precio_unitario_neto):
            self.calcular_linea(save=False)
        super().save(*args, **kwargs)
