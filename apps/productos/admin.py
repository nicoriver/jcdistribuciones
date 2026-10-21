from django.contrib import admin
from .models import Categoria, Marca, Producto, Presentacion, TipoListaPrecio, PrecioProducto


class PresentacionInline(admin.TabularInline):
    model = Presentacion
    extra = 1
    fields = ('nombre', 'factor_conversion', 'codigo_barras', 'es_default')


class PrecioProductoInline(admin.TabularInline):
    model = PrecioProducto
    extra = 1
    fields = ('tipo_lista', 'porcentaje_recargo', 'porcentaje_descuento', 'precio_neto', 'precio_final')
    readonly_fields = ('precio_final',)


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'activa', 'descripcion')
    list_filter = ('activa',)
    search_fields = ('nombre', 'descripcion')
    ordering = ('nombre',)


@admin.register(Marca)
class MarcaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'activa')
    list_filter = ('activa',)
    search_fields = ('nombre',)
    ordering = ('nombre',)


@admin.register(TipoListaPrecio)
class TipoListaPrecioAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'activa', 'descripcion')
    list_filter = ('activa',)
    search_fields = ('nombre', 'descripcion')
    ordering = ('nombre',)


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = (
        'codigo',
        'nombre',
        'categoria',
        'marca',
        'costo_base',
        'alicuota_iva',
        'stock_actual',
        'controla_stock',
        'activo'
    )
    list_filter = ('categoria', 'marca', 'alicuota_iva', 'activo', 'controla_stock')
    search_fields = ('codigo', 'codigo_barras', 'nombre', 'descripcion')
    ordering = ('nombre',)
    inlines = [PresentacionInline, PrecioProductoInline]

    fieldsets = (
        ('Identificación del Producto', {
            'fields': ('codigo', 'codigo_barras', 'nombre', 'descripcion', 'categoria', 'marca', 'proveedor_habitual', 'imagen')
        }),
        ('Formación de Costos & Fiscal', {
            'fields': ('costo_base', 'alicuota_iva')
        }),
        ('Inventario & Stock', {
            'fields': ('stock_actual', 'punto_reposicion', 'controla_stock', 'activo')
        }),
    )
