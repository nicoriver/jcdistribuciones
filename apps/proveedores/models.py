from django.db import models


class Proveedor(models.Model):
    cuit = models.CharField(
        max_length=20,
        unique=True,
        db_index=True,
        verbose_name="CUIT / CUIL",
        help_text="Identificador fiscal único (sin guiones ni puntos)"
    )
    razon_social = models.CharField(
        max_length=150,
        verbose_name="Razón Social"
    )
    domicilio = models.CharField(
        max_length=200,
        blank=True,
        default='',
        verbose_name="Domicilio"
    )
    telefono = models.CharField(
        max_length=50,
        blank=True,
        default='',
        verbose_name="Teléfono"
    )
    email = models.EmailField(
        blank=True,
        default='',
        verbose_name="Correo Electrónico"
    )
    contacto_nombre = models.CharField(
        max_length=100,
        blank=True,
        default='',
        verbose_name="Nombre de Contacto"
    )
    activo = models.BooleanField(
        default=True,
        verbose_name="Activo"
    )
    fecha_creacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de Alta"
    )

    class Meta:
        verbose_name = "Proveedor"
        verbose_name_plural = "Proveedores"
        ordering = ['razon_social']

    def __str__(self):
        return f"{self.razon_social} (CUIT {self.cuit})"

    def clean(self):
        super().clean()
        if self.cuit:
            self.cuit = self.cuit.strip().replace('-', '').replace('.', '')
