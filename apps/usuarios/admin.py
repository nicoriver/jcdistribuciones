from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import Usuario


@admin.register(Usuario)
class UsuarioAdmin(BaseUserAdmin):
    list_display = ('username', 'cuit_dni', 'nombre', 'apellido', 'email', 'rol', 'is_staff', 'is_active', 'date_joined')
    list_filter = ('rol', 'is_staff', 'is_active')
    search_fields = ('username', 'cuit_dni', 'nombre', 'apellido', 'email')
    ordering = ('-date_joined',)

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Información Personal & Fiscal', {'fields': ('nombre', 'apellido', 'cuit_dni', 'email')}),
        ('Roles & Permisos', {'fields': ('rol', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Fechas Importantes', {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'cuit_dni', 'nombre', 'apellido', 'email', 'rol', 'password1', 'password2'),
        }),
    )

    readonly_fields = ('date_joined', 'last_login')
