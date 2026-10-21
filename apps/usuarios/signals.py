from django.db.models.signals import post_migrate, post_save
from django.dispatch import receiver
from .models import Usuario
from .roles import setup_roles_and_permissions, asignar_grupo_por_rol


@receiver(post_migrate)
def on_post_migrate_setup_roles(sender, **kwargs):
    """
    Inicializa grupos y permisos automáticamente tras la migración de la app usuarios.
    """
    if sender.name == 'usuarios':
        setup_roles_and_permissions()


@receiver(post_save, sender=Usuario)
def on_usuario_saved_asignar_grupo(sender, instance, created, **kwargs):
    """
    Asigna el grupo RBAC correspondiente según el rol del usuario cada vez que se guarda.
    """
    # Evitar recursión infinita
    asignar_grupo_por_rol(instance)
