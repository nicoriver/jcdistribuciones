from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType


ROLE_GROUPS = {
    'ADMIN': 'Administrador',
    'SUPERVISOR': 'Supervisor',
    'VENDEDOR': 'Vendedor',
    'CLIENTE': 'Cliente',
}

SUPERVISOR_APPS = [
    'usuarios',
    'geografia',
    'proveedores',
    'clientes',
    'productos',
    'pedidos',
    'comprobantes',
    'stock',
    'compras',
]

VENDEDOR_PERMS = [
    ('pedidos', ['view_pedido', 'add_pedido', 'change_pedido', 'view_detallepedido', 'add_detallepedido', 'change_detallepedido']),
    ('clientes', ['view_cliente', 'view_localidad', 'view_zona', 'view_vendedor']),
    ('geografia', ['view_zona', 'view_localidad', 'view_provincia']),
    ('productos', ['view_producto', 'view_presentacion', 'view_categoria', 'view_marca', 'view_listaprecio', 'view_precioproducto']),
]

CLIENTE_PERMS = [
    ('pedidos', ['view_pedido', 'add_pedido', 'change_pedido', 'view_detallepedido', 'add_detallepedido', 'change_detallepedido', 'delete_detallepedido']),
    ('productos', ['view_producto', 'view_presentacion', 'view_categoria', 'view_marca']),
]


def setup_roles_and_permissions(stdout=None):
    """
    Crea o asegura los 4 grupos principales del sistema (Administrador, Supervisor, Vendedor, Cliente)
    y asigna sus permisos correspondientes.
    """
    def log(msg):
        if stdout:
            stdout.write(msg)
        else:
            print(msg)

    # 1. Grupo Administrador: todos los permisos
    admin_group, _ = Group.objects.get_or_create(name='Administrador')
    all_permissions = Permission.objects.all()
    admin_group.permissions.set(all_permissions)
    log("[OK] Grupo 'Administrador' configurado con permisos totales.")

    # 2. Grupo Supervisor: permisos completos sobre el dominio operativo
    supervisor_group, _ = Group.objects.get_or_create(name='Supervisor')
    supervisor_cts = ContentType.objects.filter(app_label__in=SUPERVISOR_APPS)
    supervisor_permissions = Permission.objects.filter(content_type__in=supervisor_cts)
    supervisor_group.permissions.set(supervisor_permissions)
    log(f"[OK] Grupo 'Supervisor' configurado con {supervisor_permissions.count()} permisos operativos.")

    # 3. Grupo Vendedor: gestión de pedidos y consulta de catálogo/clientes
    vendedor_group, _ = Group.objects.get_or_create(name='Vendedor')
    vendedor_perms_qs = Permission.objects.none()
    for app_label, codenames in VENDEDOR_PERMS:
        cts = ContentType.objects.filter(app_label=app_label)
        vendedor_perms_qs |= Permission.objects.filter(content_type__in=cts, codename__in=codenames)
    vendedor_group.permissions.set(vendedor_perms_qs)
    log(f"[OK] Grupo 'Vendedor' configurado con {vendedor_perms_qs.count()} permisos.")

    # 4. Grupo Cliente: consulta de catálogo y emisión de pedidos portal
    cliente_group, _ = Group.objects.get_or_create(name='Cliente')
    cliente_perms_qs = Permission.objects.none()
    for app_label, codenames in CLIENTE_PERMS:
        cts = ContentType.objects.filter(app_label=app_label)
        cliente_perms_qs |= Permission.objects.filter(content_type__in=cts, codename__in=codenames)
    cliente_group.permissions.set(cliente_perms_qs)
    log(f"[OK] Grupo 'Cliente' configurado con {cliente_perms_qs.count()} permisos.")

    return {
        'admin': admin_group,
        'supervisor': supervisor_group,
        'vendedor': vendedor_group,
        'cliente': cliente_group,
    }


def asignar_grupo_por_rol(usuario):
    """
    Sincroniza el grupo RBAC y flags (is_staff) del usuario según su campo 'rol'.
    """
    if not usuario.pk:
        return

    # Determinar grupo destino
    nombre_grupo = None
    if usuario.rol == 'ADMIN':
        nombre_grupo = 'Administrador'
        if not usuario.is_staff:
            usuario.is_staff = True
            usuario.save(update_fields=['is_staff'])
    elif usuario.rol in ['SUPERVISOR', 'FACTURACION', 'DEPOSITO']:
        nombre_grupo = 'Supervisor'
        if not usuario.is_staff:
            usuario.is_staff = True
            usuario.save(update_fields=['is_staff'])
    elif usuario.rol == 'VENDEDOR':
        nombre_grupo = 'Vendedor'
    elif usuario.rol == 'CLIENTE':
        nombre_grupo = 'Cliente'

    if nombre_grupo:
        grupo, _ = Group.objects.get_or_create(name=nombre_grupo)
        # Limpiar grupos anteriores y asignar el nuevo
        usuario.groups.set([grupo])


def sincronizar_usuarios_existentes(stdout=None):
    """
    Recorre todos los usuarios de la base de datos y les asigna su grupo correspondiente.
    """
    from usuarios.models import Usuario
    for user in Usuario.objects.all():
        asignar_grupo_por_rol(user)
    if stdout:
        stdout.write("[OK] Todos los usuarios sincronizados con sus grupos RBAC.")
