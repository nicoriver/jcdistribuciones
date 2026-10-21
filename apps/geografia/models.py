from django.db import models


class Provincia(models.Model):
    nombre = models.CharField(max_length=100, unique=True, verbose_name="Provincia")

    class Meta:
        verbose_name = "Provincia"
        verbose_name_plural = "Provincias"
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class Localidad(models.Model):
    provincia = models.ForeignKey(
        Provincia,
        on_delete=models.CASCADE,
        related_name='localidades',
        verbose_name="Provincia"
    )
    nombre = models.CharField(max_length=100, verbose_name="Localidad")
    codigo_postal = models.CharField(max_length=10, blank=True, verbose_name="Código Postal")

    class Meta:
        verbose_name = "Localidad"
        verbose_name_plural = "Localidades"
        ordering = ['nombre']
        unique_together = ('provincia', 'nombre')

    def __str__(self):
        return f"{self.nombre} ({self.provincia.nombre})"


class Zona(models.Model):
    nombre = models.CharField(max_length=100, unique=True, verbose_name="Nombre de Zona")
    descripcion = models.CharField(max_length=200, blank=True, verbose_name="Descripción")
    dia_reparto_defecto = models.CharField(
        max_length=100,
        blank=True,
        default='',
        verbose_name="Día de Reparto por Defecto",
        help_text='Días habituales de reparto: ej. "Lunes y Jueves"'
    )
    activa = models.BooleanField(default=True, verbose_name="Activa")

    class Meta:
        verbose_name = "Zona"
        verbose_name_plural = "Zonas"
        ordering = ['nombre']

    def __str__(self):
        return self.nombre
