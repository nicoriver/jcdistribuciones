from django.contrib import admin
from .models import Compra, DetalleCompra
from .services import CompraService


class DetalleCompraInline(admin.TabularInline):
    model = DetalleCompra
    extra = 1
    fields = ('producto', 'cantidad', 'precio_costo_unitario', 'subtotal')
    readonly_fields = ('subtotal',)


@admin.register(Compra)
class CompraAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'nro_comprobante_proveedor',
        'proveedor',
        'fecha_emision',
        'total_compra',
        'usuario',
    )
    list_filter = ('proveedor', 'fecha_emision', 'usuario')
    search_fields = (
        'nro_comprobante_proveedor',
        'proveedor__razon_social',
        'proveedor__cuit',
        'observaciones',
    )
    date_hierarchy = 'fecha_emision'
    inlines = [DetalleCompraInline]
    readonly_fields = ('fecha_emision', 'total_compra')

    def save_model(self, request, obj, form, change):
        if not change and not obj.usuario_id:
            obj.usuario = request.user
        super().save_model(request, obj, form, change)


@admin.register(DetalleCompra)
class DetalleCompraAdmin(admin.ModelAdmin):
    list_display = ('id', 'compra', 'producto', 'cantidad', 'precio_costo_unitario', 'subtotal')
    list_filter = ('compra__proveedor', 'producto')
    search_fields = ('compra__nro_comprobante_proveedor', 'producto__nombre', 'producto__codigo')
