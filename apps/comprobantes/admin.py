from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from django.shortcuts import redirect
from .models import PuntoVentaNumerador, Remito, DetalleRemito, NotaCreditoInterna, DetalleNotaCredito


@admin.register(PuntoVentaNumerador)
class PuntoVentaNumeradorAdmin(admin.ModelAdmin):
    list_display = ('punto_venta', 'tipo_documento', 'ultimo_numero')
    list_filter = ('punto_venta', 'tipo_documento')


class DetalleRemitoInline(admin.TabularInline):
    model = DetalleRemito
    extra = 0
    fields = (
        'producto',
        'presentacion',
        'factor_unidades',
        'codigo_historico',
        'descripcion_historica',
        'cantidad',
        'precio_unitario_historico',
        'porcentaje_descuento',
        'subtotal',
        'cantidad_devuelta',
    )
    readonly_fields = (
        'codigo_historico',
        'descripcion_historica',
        'precio_unitario_historico',
        'subtotal',
        'cantidad_devuelta',
    )


@admin.register(Remito)
class RemitoAdmin(admin.ModelAdmin):
    list_display = (
        'numero_completo',
        'fecha_emision',
        'cliente',
        'vendedor',
        'supervisor',
        'subtotal_bruto',
        'total_descuento',
        'monto_total',
        'anulado',
        'boton_impresion_a4',
    )
    list_filter = ('vendedor', 'fecha_emision', 'anulado', 'estado', 'punto_venta')
    search_fields = (
        'numero_completo',
        'cliente__razon_social',
        'cliente__cuit',
        'cliente__nombre_fantasia',
    )
    date_hierarchy = 'fecha_emision'
    inlines = [DetalleRemitoInline]
    readonly_fields = (
        'numero_completo',
        'fecha_emision',
        'subtotal_bruto',
        'total_descuento',
        'monto_total',
    )
    actions = ['abrir_impresion_a4_action']

    @admin.display(description="Impresión A4")
    def boton_impresion_a4(self, obj):
        if obj.pk:
            url = reverse('comprobantes:imprimir_remito', kwargs={'remito_id': obj.pk})
            return format_html(
                '<a class="button" href="{}" target="_blank" style="padding:3px 8px; background:#2563eb; color:#fff; border-radius:4px; text-decoration:none;">🖨️ Imprimir A4</a>',
                url
            )
        return "-"

    @admin.action(description="Abrir vista de impresión A4 del Remito seleccionado")
    def abrir_impresion_a4_action(self, request, queryset):
        remito = queryset.first()
        if remito:
            return redirect('comprobantes:imprimir_remito', remito_id=remito.pk)


class DetalleNotaCreditoInline(admin.TabularInline):
    model = DetalleNotaCredito
    extra = 0
    fields = ('detalle_remito', 'cantidad', 'precio_unitario', 'total_linea')
    readonly_fields = ('precio_unitario', 'total_linea')


@admin.register(NotaCreditoInterna)
class NotaCreditoInternaAdmin(admin.ModelAdmin):
    list_display = (
        'numero_nc',
        'remito',
        'motivo_tipo',
        'reingresa_stock',
        'monto_total',
        'fecha',
        'usuario',
    )
    list_filter = ('motivo_tipo', 'reingresa_stock', 'fecha')
    search_fields = ('numero_nc', 'remito__numero_completo', 'remito__cliente__razon_social')
    inlines = [DetalleNotaCreditoInline]
    readonly_fields = ('numero_nc', 'fecha', 'monto_total')
