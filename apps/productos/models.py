from decimal import Decimal, ROUND_HALF_UP
from django.db import models


IVA_CHOICES = [
    (Decimal('0.00'), '0.00% (Exento)'),
    (Decimal('10.50'), '10.50% (Reducido)'),
    (Decimal('21.00'), '21.00% (General)'),
    (Decimal('27.00'), '27.00% (Incrementado)'),
]


class Categoria(models.Model):
    nombre = models.CharField(max_length=100, unique=True, verbose_name="Nombre de Categoría")
    descripcion = models.CharField(max_length=200, blank=True, default='', verbose_name="Descripción")
    activa = models.BooleanField(default=True, verbose_name="Activa")

    class Meta:
        verbose_name = "Categoría"
        verbose_name_plural = "Categorías"
        ordering = ['nombre']

    def __str__(self):
        return self.nombre

    # Compatibilidad
    @property
    def activo(self):
        return self.activa

    @activo.setter
    def activo(self, val):
        self.activa = val


class Marca(models.Model):
    nombre = models.CharField(max_length=100, unique=True, verbose_name="Nombre de Marca")
    activa = models.BooleanField(default=True, verbose_name="Activa")

    class Meta:
        verbose_name = "Marca"
        verbose_name_plural = "Marcas"
        ordering = ['nombre']

    def __str__(self):
        return self.nombre

    # Compatibilidad
    @property
    def activo(self):
        return self.activa

    @activo.setter
    def activo(self, val):
        self.activa = val


class AlicuotaIVA(models.Model):
    """Modelo auxiliar de alícuotas mantenido por retrocompatibilidad."""
    porcentaje = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        unique=True,
        verbose_name="% Alícuota IVA"
    )
    descripcion = models.CharField(max_length=50, verbose_name="Descripción")

    class Meta:
        verbose_name = "Alícuota de IVA"
        verbose_name_plural = "Alícuotas de IVA"
        ordering = ['porcentaje']

    def __str__(self):
        return f"{self.porcentaje}% - {self.descripcion}"


class Producto(models.Model):
    codigo = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        verbose_name="Código Interno"
    )
    codigo_barras = models.CharField(
        max_length=50,
        blank=True,
        default='',
        db_index=True,
        verbose_name="Código de Barras"
    )
    nombre = models.CharField(
        max_length=150,
        db_index=True,
        verbose_name="Nombre del Producto"
    )
    descripcion = models.TextField(blank=True, default='', verbose_name="Descripción")
    categoria = models.ForeignKey(
        Categoria,
        on_delete=models.PROTECT,
        related_name='productos',
        verbose_name="Categoría"
    )
    marca = models.ForeignKey(
        Marca,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='productos',
        verbose_name="Marca"
    )
    proveedor_habitual = models.ForeignKey(
        'proveedores.Proveedor',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='productos',
        verbose_name="Proveedor Habitual"
    )
    imagen = models.ImageField(
        upload_to='productos/',
        null=True,
        blank=True,
        verbose_name="Imagen"
    )
    alicuota_iva = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        choices=IVA_CHOICES,
        default=Decimal('21.00'),
        verbose_name="% Alícuota IVA"
    )
    costo_base = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Precio de Costo Base"
    )
    stock_actual = models.IntegerField(
        default=0,
        verbose_name="Stock Actual"
    )
    punto_reposicion = models.IntegerField(
        default=0,
        verbose_name="Punto de Reposición (Stock Mínimo)"
    )
    controla_stock = models.BooleanField(default=True, verbose_name="Controla Stock")
    activo = models.BooleanField(default=True, verbose_name="Activo")

    class Meta:
        verbose_name = "Producto"
        verbose_name_plural = "Productos"
        ordering = ['nombre']

    def __str__(self):
        return f"[{self.codigo}] {self.nombre}"

    def __init__(self, *args, **kwargs):
        if 'alicuota_iva' in kwargs and isinstance(kwargs['alicuota_iva'], AlicuotaIVA):
            kwargs['alicuota_iva'] = kwargs['alicuota_iva'].porcentaje
        super().__init__(*args, **kwargs)

    def clean(self):
        super().clean()
        if isinstance(self.alicuota_iva, AlicuotaIVA):
            self.alicuota_iva = self.alicuota_iva.porcentaje

    def save(self, *args, **kwargs):
        if isinstance(self.alicuota_iva, AlicuotaIVA):
            self.alicuota_iva = self.alicuota_iva.porcentaje
        super().save(*args, **kwargs)

    # Compatibilidad con atributos previos
    @property
    def costo(self):
        return self.costo_base

    @costo.setter
    def costo(self, val):
        self.costo_base = val

    @property
    def codigo_barra(self):
        return self.codigo_barras

    @codigo_barra.setter
    def codigo_barra(self, val):
        self.codigo_barras = val


class Presentacion(models.Model):
    producto = models.ForeignKey(
        Producto,
        on_delete=models.CASCADE,
        related_name='presentaciones',
        verbose_name="Producto"
    )
    nombre = models.CharField(
        max_length=50,
        verbose_name="Nombre Presentación",
        help_text="Ej: Unidad, Pack x6, Caja x24"
    )
    factor_conversion = models.IntegerField(
        default=1,
        verbose_name="Factor de Conversión",
        help_text="Cantidad de unidades base que contiene esta presentación"
    )
    codigo_barras = models.CharField(
        max_length=50,
        blank=True,
        default='',
        verbose_name="Código de Barras de Presentación"
    )
    es_default = models.BooleanField(
        default=False,
        verbose_name="Es Presentación por Defecto"
    )

    class Meta:
        verbose_name = "Presentación de Producto"
        verbose_name_plural = "Presentaciones de Productos"

    def __str__(self):
        return f"{self.producto.nombre} - {self.nombre} (x{self.factor_conversion})"

    # Compatibilidad
    @property
    def factor_unidades(self):
        return Decimal(str(self.factor_conversion))

    @factor_unidades.setter
    def factor_unidades(self, val):
        self.factor_conversion = int(val)

    @property
    def codigo_barra(self):
        return self.codigo_barras

    @codigo_barra.setter
    def codigo_barra(self, val):
        self.codigo_barras = val


class TipoListaPrecio(models.Model):
    nombre = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="Nombre de Lista",
        help_text="Ej: Mayorista, Distribuidor, Especial"
    )
    descripcion = models.CharField(
        max_length=150,
        blank=True,
        default='',
        verbose_name="Descripción"
    )
    activa = models.BooleanField(
        default=True,
        verbose_name="Activa"
    )

    class Meta:
        verbose_name = "Tipo de Lista de Precios"
        verbose_name_plural = "Tipos de Listas de Precios"
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


# Alias de retrocompatibilidad
ListaPrecio = TipoListaPrecio


class PrecioProducto(models.Model):
    producto = models.ForeignKey(
        Producto,
        on_delete=models.CASCADE,
        related_name='precios',
        verbose_name="Producto"
    )
    tipo_lista = models.ForeignKey(
        TipoListaPrecio,
        on_delete=models.CASCADE,
        related_name='precios_productos',
        verbose_name="Tipo de Lista"
    )
    porcentaje_recargo = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="% Recargo / Margen"
    )
    porcentaje_descuento = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="% Descuento Comercial"
    )
    precio_neto = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Precio Neto Gravado (sin IVA)",
        help_text="Precio gravado sin IVA"
    )
    precio_final = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Precio Final de Venta"
    )
    actualizado_en = models.DateTimeField(
        auto_now=True,
        verbose_name="Última Actualización"
    )

    class Meta:
        verbose_name = "Precio de Producto en Lista"
        verbose_name_plural = "Precios de Productos en Listas"
        unique_together = ('producto', 'tipo_lista')

    def __str__(self):
        return f"{self.producto.nombre} @ {self.tipo_lista.nombre}: Neto ${self.precio_neto} (Final: ${self.precio_final})"

    # Compatibilidad con código previo
    @property
    def lista(self):
        return self.tipo_lista

    @lista.setter
    def lista(self, val):
        self.tipo_lista = val

    @property
    def recargo_porcentaje(self):
        return self.porcentaje_recargo

    @recargo_porcentaje.setter
    def recargo_porcentaje(self, val):
        self.porcentaje_recargo = val

    @property
    def descuento_porcentaje(self):
        return self.porcentaje_descuento

    @descuento_porcentaje.setter
    def descuento_porcentaje(self, val):
        self.porcentaje_descuento = val

    def calcular_y_guardar(self, save=True):
        from .services import CalculadoraPreciosService
        costo = self.producto.costo_base or Decimal('0.00')
        recargo = self.porcentaje_recargo or Decimal('0.00')
        descuento = self.porcentaje_descuento or Decimal('0.00')
        iva = self.producto.alicuota_iva or Decimal('21.00')

        # 1. Precio neto gravado (sin IVA) = costo * (1 + recargo / 100)
        p_neto = costo * (Decimal('1.00') + (recargo / Decimal('100.00')))
        self.precio_neto = p_neto.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        # 2. Precio final con IVA y descuento
        self.precio_final = CalculadoraPreciosService.calcular_precio_final(costo, recargo, iva, descuento)

        if save:
            self.save()
        return self.precio_final

    def save(self, *args, **kwargs):
        if not self.pk or (self.precio_neto == Decimal('0.00') and self.producto.costo_base > Decimal('0.00')):
            costo = self.producto.costo_base or Decimal('0.00')
            recargo = self.porcentaje_recargo or Decimal('0.00')
            descuento = self.porcentaje_descuento or Decimal('0.00')
            iva = self.producto.alicuota_iva or Decimal('21.00')
            from .services import CalculadoraPreciosService
            p_neto = costo * (Decimal('1.00') + (recargo / Decimal('100.00')))
            self.precio_neto = p_neto.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            self.precio_final = CalculadoraPreciosService.calcular_precio_final(costo, recargo, iva, descuento)
        super().save(*args, **kwargs)
