from decimal import Decimal
from django.db import models
from geografia.models import Provincia, Localidad, Zona


class Vendedor(models.Model):
    usuario = models.OneToOneField(
        'usuarios.Usuario',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='perfil_vendedor',
        verbose_name="Usuario Asociado"
    )
    legajo = models.CharField(
        max_length=50,
        unique=True,
        null=True,
        blank=True,
        verbose_name="Legajo"
    )
    nombre = models.CharField(max_length=100, blank=True, default='', verbose_name="Nombre")
    apellido = models.CharField(max_length=100, blank=True, default='', verbose_name="Apellido")
    dni = models.CharField(max_length=20, blank=True, default='', verbose_name="DNI")
    telefono = models.CharField(max_length=50, blank=True, default='', verbose_name="Teléfono")
    comision_porcentaje = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="% Comisión"
    )
    activo = models.BooleanField(default=True, verbose_name="Activo")

    zonas = models.ManyToManyField(
        'geografia.Zona',
        through='AsignacionZonaVendedor',
        related_name='vendedores',
        blank=True,
        verbose_name="Zonas Asignadas"
    )

    class Meta:
        verbose_name = "Vendedor"
        verbose_name_plural = "Vendedores"
        ordering = ['apellido', 'nombre']

    def __str__(self):
        if self.apellido or self.nombre:
            return f"{self.apellido}, {self.nombre}".strip(', ')
        if self.usuario:
            return self.usuario.get_full_name() or self.usuario.username or f"Vendedor #{self.pk}"
        return f"Vendedor #{self.pk}"

    def nombre_completo(self):
        if self.nombre or self.apellido:
            return f"{self.nombre} {self.apellido}".strip()
        if self.usuario:
            return self.usuario.get_full_name()
        return f"Vendedor #{self.pk}"


class AsignacionZonaVendedor(models.Model):
    vendedor = models.ForeignKey(
        Vendedor,
        on_delete=models.CASCADE,
        related_name='asignaciones_zona',
        verbose_name="Vendedor"
    )
    zona = models.ForeignKey(
        'geografia.Zona',
        on_delete=models.CASCADE,
        related_name='asignaciones_vendedor',
        verbose_name="Zona"
    )
    activo = models.BooleanField(
        default=True,
        help_text="Permite activar o desasignar la zona al vendedor",
        verbose_name="Activo"
    )
    fecha_asignacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha Asignación")
    observaciones = models.CharField(max_length=200, blank=True, default='', verbose_name="Observaciones")

    class Meta:
        verbose_name = "Asignación de Zona a Vendedor"
        verbose_name_plural = "Asignaciones de Zonas a Vendedores"
        unique_together = ('vendedor', 'zona')

    def __str__(self):
        estado_str = "Activa" if self.activo else "Inactiva"
        return f"{self.vendedor} -> {self.zona} ({estado_str})"


class CondicionIVA(models.Model):
    codigo = models.CharField(max_length=10, unique=True, verbose_name="Código")
    descripcion = models.CharField(max_length=100, verbose_name="Descripción")
    discrimina_iva = models.BooleanField(default=False, verbose_name="Discrimina IVA")

    class Meta:
        verbose_name = "Condición de IVA"
        verbose_name_plural = "Condiciones de IVA"
        ordering = ['codigo']

    def __str__(self):
        return f"{self.codigo} - {self.descripcion}"


class ClienteQuerySet(models.QuerySet):
    def para_usuario(self, user):
        """
        Filtra clientes según el rol del usuario autenticado:
        - Admin, Supervisor, Facturación, Depósito o Staff: visibilidad completa de la cartera.
        - Vendedor: visibilidad restringida exclusivamente a sus clientes asignados.
        - Otros o no autenticados: conjunto vacío.
        """
        if not user or not user.is_authenticated:
            return self.none()
        if user.is_superuser or user.is_staff or getattr(user, 'rol', None) in ['ADMIN', 'SUPERVISOR', 'FACTURACION', 'DEPOSITO']:
            return self.all()
        if getattr(user, 'rol', None) == 'VENDEDOR' or hasattr(user, 'perfil_vendedor'):
            return self.filter(vendedor__usuario=user)
        return self.none()


class ClienteManager(models.Manager):
    def get_queryset(self):
        return ClienteQuerySet(self.model, using=self._db)

    def para_usuario(self, user):
        return self.get_queryset().para_usuario(user)


class Cliente(models.Model):
    DIAS_REPARTO = [
        (1, 'Lunes'),
        (2, 'Martes'),
        (3, 'Miércoles'),
        (4, 'Jueves'),
        (5, 'Viernes'),
        (6, 'Sábado'),
    ]

    ESTADOS = [
        ('PENDIENTE', 'Pendiente de Aprobación'),
        ('ACTIVO', 'Activo'),
        ('INACTIVO', 'Inactivo'),
    ]

    usuario = models.OneToOneField(
        'usuarios.Usuario',
        on_delete=models.CASCADE,
        related_name='perfil_cliente',
        verbose_name="Usuario de Portal",
        null=True,
        blank=True
    )
    cuit = models.CharField(
        max_length=20,
        unique=True,
        db_index=True,
        verbose_name="CUIT"
    )
    razon_social = models.CharField(max_length=150, verbose_name="Razón Social")
    nombre_fantasia = models.CharField(max_length=150, blank=True, default='', verbose_name="Nombre de Fantasía")
    domicilio = models.CharField(max_length=150, verbose_name="Domicilio Comercial")
    condicion_iva = models.ForeignKey(
        CondicionIVA,
        on_delete=models.PROTECT,
        related_name='clientes',
        verbose_name="Condición IVA",
        null=True,
        blank=True
    )
    zona = models.ForeignKey(
        'geografia.Zona',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='clientes',
        verbose_name="Zona Logística"
    )
    vendedor = models.ForeignKey(
        Vendedor,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='clientes',
        verbose_name="Vendedor Asignado"
    )
    localidad = models.ForeignKey(
        'geografia.Localidad',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='clientes',
        verbose_name="Localidad"
    )

    # Campos de contacto
    telefono = models.CharField(max_length=50, blank=True, default='', verbose_name="Teléfono")
    telefono_alt = models.CharField(max_length=50, blank=True, default='', verbose_name="Teléfono Alternativo")
    email = models.EmailField(blank=True, default='', verbose_name="Correo Electrónico")
    contacto = models.CharField(max_length=100, blank=True, default='', verbose_name="Persona de Contacto")

    # Campos logísticos y comerciales
    latitud = models.DecimalField(
        max_digits=12,
        decimal_places=8,
        null=True,
        blank=True,
        verbose_name="Latitud GPS"
    )
    longitud = models.DecimalField(
        max_digits=12,
        decimal_places=8,
        null=True,
        blank=True,
        verbose_name="Longitud GPS"
    )
    saldo_cta_cte_inicial = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Saldo Cta. Cte. Inicial"
    )
    activo = models.BooleanField(
        default=True,
        verbose_name="Activo"
    )
    dia_reparto = models.IntegerField(
        choices=DIAS_REPARTO,
        null=True,
        blank=True,
        verbose_name="Día Fijo de Reparto"
    )
    estado = models.CharField(
        max_length=20,
        choices=ESTADOS,
        default='ACTIVO',
        verbose_name="Estado de Cuenta"
    )
    monto_minimo_pedido = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Monto Mínimo por Pedido"
    )
    tipo_lista_precio = models.ForeignKey(
        'productos.TipoListaPrecio',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='clientes',
        verbose_name="Tipo de Lista de Precios"
    )

    objects = ClienteManager()

    @property
    def lista_precio_default(self):
        return self.tipo_lista_precio

    @lista_precio_default.setter
    def lista_precio_default(self, val):
        self.tipo_lista_precio = val

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
        ordering = ['razon_social']

    def __str__(self):
        return f"{self.razon_social} (CUIT {self.cuit})"

    def clean(self):
        super().clean()
        if self.cuit:
            self.cuit = self.cuit.strip().replace('-', '').replace('.', '')
