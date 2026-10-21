from django.contrib import admin
from .models import Pedido, DetallePedido
from .services import PedidoService


class DetallePedidoInline(admin.TabularInline):
    model = DetallePedido
    extra = 0
    fields = (
        'producto', 'presentacion', 'cantidad', 'factor_unidades',
        'precio_unitario', 'porcentaje_descuento', 'subtotal', 'supera_stock_disponible'
    )
    readonly_fields = (
        'subtotal', 'supera_stock_disponible'
    )

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.estado in ['FACTURADO_REMITO', 'FACTURADO']:
            return [field.name for field in self.model._meta.fields]
        return super().get_readonly_fields(request, obj)


@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = ('numero_pedido', 'cliente', 'vendedor', 'estado', 'total_estimado', 'fecha_creacion')
    list_filter = ('estado', 'vendedor', 'fecha_creacion')
    search_fields = ('numero_pedido', 'cliente__razon_social', 'cliente__cuit')
    readonly_fields = (
        'numero_pedido', 'monto_subtotal_neto', 'monto_iva_total',
        'total_estimado', 'fecha_creacion', 'fecha_envio',
        'aprobado_por', 'fecha_aprobacion', 'remito_asociado_id'
    )
    inlines = [DetallePedidoInline]
    actions = ['emitir_remito_action']

    fieldsets = (
        ('Identificación del Pedido', {
            'fields': ('numero_pedido', 'cliente', 'vendedor', 'lista_precio', 'estado', 'remito_asociado_id')
        }),
        ('Totales Monetarios', {
            'fields': ('monto_subtotal_neto', 'monto_iva_total', 'total_estimado')
        }),
        ('Observaciones y Auditoría', {
            'fields': (
                'observaciones', 'motivo_rechazo',
                'aprobado_por', 'fecha_aprobacion', 'fecha_creacion', 'fecha_envio'
            )
        }),
    )

    @admin.action(description="Emitir Remito A4 y Despachar Pedidos Seleccionados")
    def emitir_remito_action(self, request, queryset):
        aprobados = queryset.filter(estado='APROBADO')
        count = 0
        errores = 0

        for pedido in aprobados:
            try:
                PedidoService.facturar_pedido_a_remito(pedido, request.user)
                count += 1
            except Exception:
                errores += 1

        if count > 0:
            self.message_user(request, f"Se emitieron {count} remito(s) de despacho correctamente.")
        if errores > 0:
            self.message_user(request, f"Hubo {errores} error(es) al emitir remitos.", level='WARNING')
        if count == 0 and errores == 0:
            self.message_user(request, "Ninguno de los pedidos seleccionados estaba en estado APROBADO.", level='WARNING')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs

        if hasattr(request.user, 'rol') and request.user.rol == 'VENDEDOR':
            return qs.filter(vendedor__usuario=request.user)

        return qs
