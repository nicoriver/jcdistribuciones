from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from .managers import CustomUserManager


class Usuario(AbstractBaseUser, PermissionsMixin):
    """
    Modelo de Usuario Personalizado para JC Distribuciones.
    Soporta autenticación dual (CUIT/DNI o Username) y RBAC por roles y grupos.
    """

    ROLES = [
        ('ADMIN', 'Administrador'),
        ('SUPERVISOR', 'Supervisor'),
        ('VENDEDOR', 'Vendedor'),
        ('CLIENTE', 'Cliente Portal'),
        # Roles legacy mantenidos para retrocompatibilidad
        ('FACTURACION', 'Facturación (Legacy)'),
        ('DEPOSITO', 'Depósito (Legacy)'),
        ('CONSULTA', 'Consulta y Reportes (Legacy)'),
    ]

    username = models.CharField(
        max_length=50,
        unique=True,
        null=True,
        blank=True,
        verbose_name='Nombre de usuario',
        help_text='Identificador único para operadores internos'
    )
    cuit_dni = models.CharField(
        max_length=20,
        unique=True,
        null=True,
        blank=True,
        db_index=True,
        verbose_name='CUIT / DNI',
        help_text='Identificador numérico único para clientes o personal (sin guiones ni puntos)'
    )
    email = models.EmailField(
        unique=True,
        null=True,
        blank=True,
        verbose_name='Correo electrónico'
    )
    nombre = models.CharField(
        max_length=100,
        blank=True,
        default='',
        verbose_name='Nombre'
    )
    apellido = models.CharField(
        max_length=100,
        blank=True,
        default='',
        verbose_name='Apellido'
    )
    rol = models.CharField(
        max_length=20,
        choices=ROLES,
        default='CLIENTE',
        verbose_name='Rol en el sistema'
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name='Activo'
    )
    is_staff = models.BooleanField(
        default=False,
        verbose_name='Es Staff (Acceso Admin)'
    )
    date_joined = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de registro'
    )

    objects = CustomUserManager()

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email']

    class Meta:
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'
        ordering = ['-date_joined']

    def __str__(self):
        ident = self.username or self.cuit_dni or self.email or f"ID {self.pk}"
        nom = self.nombre_completo
        return f"{ident} - {nom} ({self.get_rol_display()})" if nom else f"{ident} ({self.get_rol_display()})"

    # --------------------------------------------------------------------------
    # Propiedades de compatibilidad
    # --------------------------------------------------------------------------
    @property
    def cuit(self):
        """Compatibilidad con código legacy que referencie user.cuit."""
        return self.cuit_dni

    @cuit.setter
    def cuit(self, value):
        self.cuit_dni = value

    @property
    def nombre_completo(self):
        """Nombre completo o razón social calculada."""
        full = f"{self.nombre} {self.apellido}".strip()
        return full or self.username or (self.cuit_dni or '')

    @nombre_completo.setter
    def nombre_completo(self, value):
        if value:
            parts = str(value).strip().split(' ', 1)
            self.nombre = parts[0]
            self.apellido = parts[1] if len(parts) > 1 else ''
        else:
            self.nombre = ''
            self.apellido = ''

    def get_full_name(self):
        return self.nombre_completo

    def get_short_name(self):
        return self.nombre or self.username or (self.cuit_dni or '')

    # --------------------------------------------------------------------------
    # Helpers de Roles
    # --------------------------------------------------------------------------
    @property
    def es_administrador(self):
        return self.rol == 'ADMIN' or self.is_superuser

    @property
    def es_supervisor(self):
        return self.rol in ['SUPERVISOR', 'ADMIN', 'FACTURACION', 'DEPOSITO'] or self.is_superuser

    @property
    def es_vendedor(self):
        return self.rol == 'VENDEDOR'

    @property
    def es_cliente(self):
        return self.rol == 'CLIENTE'

    def clean(self):
        super().clean()
        if self.cuit_dni:
            self.cuit_dni = self.cuit_dni.strip().replace('-', '').replace('.', '')
        if self.username:
            self.username = self.username.strip()
        if self.email:
            self.email = self.email.strip().lower()
