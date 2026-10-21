from django.contrib import admin
from .models import Vendedor, AsignacionZonaVendedor, CondicionIVA, Cliente


class AsignacionZonaVendedorInline(admin.TabularInline):
    model = AsignacionZonaVendedor
    extra = 1


@admin.register(Vendedor)
class VendedorAdmin(admin.ModelAdmin):
    list_display = ('legajo', 'nombre_completo', 'usuario', 'telefono', 'comision_porcentaje', 'activo')
    list_filter = ('activo',)
    search_fields = ('legajo', 'nombre', 'apellido', 'dni', 'telefono')
    ordering = ('apellido', 'nombre')
    inlines = [AsignacionZonaVendedorInline]


@admin.register(CondicionIVA)
class CondicionIVAAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'descripcion', 'discrimina_iva')
    ordering = ('codigo',)


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = (
        'cuit',
        'razon_social',
        'nombre_fantasia',
        'zona',
        'vendedor',
        'telefono',
        'saldo_cta_cte_inicial',
        'activo',
        'estado'
    )
    list_filter = ('zona', 'vendedor', 'activo', 'estado')
    search_fields = ('cuit', 'razon_social', 'nombre_fantasia', 'contacto', 'email')
    ordering = ('razon_social',)

    fieldsets = (
        ('Información Principal', {
            'fields': ('cuit', 'razon_social', 'nombre_fantasia', 'usuario', 'activo', 'estado')
        }),
        ('Ubicación & Asignación Comercial', {
            'fields': ('zona', 'vendedor', 'localidad', 'domicilio', 'dia_reparto')
        }),
        ('Contacto', {
            'fields': ('telefono', 'telefono_alt', 'email', 'contacto')
        }),
        ('Condiciones Comerciales', {
            'fields': ('condicion_iva', 'tipo_lista_precio', 'monto_minimo_pedido', 'saldo_cta_cte_inicial')
        }),
        ('Geolocalización', {
            'classes': ('collapse',),
            'fields': ('latitud', 'longitud')
        }),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.para_usuario(request.user)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # Si es un vendedor que no es admin/supervisor, preseleccionar solo su perfil de vendedor
        if db_field.name == "vendedor" and not (
            request.user.is_superuser or getattr(request.user, 'rol', None) in ['ADMIN', 'SUPERVISOR']
        ):
            if hasattr(request.user, 'perfil_vendedor'):
                kwargs["queryset"] = Vendedor.objects.filter(id=request.user.perfil_vendedor.id)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
