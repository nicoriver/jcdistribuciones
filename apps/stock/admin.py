from django.contrib import admin
from .models import MovimientoStock, ConfiguracionStock


@admin.register(MovimientoStock)
class MovimientoStockAdmin(admin.ModelAdmin):
    list_display = (
        'fecha',
        'producto',
        'tipo_movimiento',
        'cantidad',
        'stock_anterior',
        'stock_resultante',
        'documento_referencia',
        'usuario',
    )
    list_filter = ('tipo_movimiento', 'fecha', 'usuario')
    search_fields = (
        'producto__nombre',
        'producto__codigo',
        'documento_referencia',
        'motivo',
        'observaciones',
    )
    readonly_fields = (
        'producto',
        'tipo_movimiento',
        'cantidad',
        'stock_anterior',
        'stock_resultante',
        'documento_referencia',
        'motivo',
        'observaciones',
        'usuario',
        'fecha',
    )
    date_hierarchy = 'fecha'
    ordering = ('-fecha',)

    def has_add_permission(self, request):
        # El Kardex es inmutable y sólo lectura para evitar manipulación arbitraria
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ConfiguracionStock)
class ConfiguracionStockAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'control_stock_habilitado', 'permitir_stock_negativo_con_alerta')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
