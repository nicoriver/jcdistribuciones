from django.contrib import admin
from .models import Proveedor


@admin.register(Proveedor)
class ProveedorAdmin(admin.ModelAdmin):
    list_display = ('cuit', 'razon_social', 'telefono', 'email', 'contacto_nombre', 'activo', 'fecha_creacion')
    list_filter = ('activo',)
    search_fields = ('cuit', 'razon_social', 'contacto_nombre', 'email')
    ordering = ('razon_social',)
