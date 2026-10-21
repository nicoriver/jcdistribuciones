from django.contrib import admin
from .models import Provincia, Localidad, Zona


@admin.register(Provincia)
class ProvinciaAdmin(admin.ModelAdmin):
    list_display = ('nombre',)
    search_fields = ('nombre',)
    ordering = ('nombre',)


@admin.register(Localidad)
class LocalidadAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'provincia', 'codigo_postal')
    list_filter = ('provincia',)
    search_fields = ('nombre', 'codigo_postal')
    ordering = ('nombre',)


@admin.register(Zona)
class ZonaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'dia_reparto_defecto', 'activa', 'descripcion')
    list_filter = ('activa',)
    search_fields = ('nombre', 'descripcion', 'dia_reparto_defecto')
    ordering = ('nombre',)
