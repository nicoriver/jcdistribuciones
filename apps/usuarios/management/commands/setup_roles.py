from django.core.management.base import BaseCommand
from usuarios.roles import setup_roles_and_permissions, sincronizar_usuarios_existentes


class Command(BaseCommand):
    help = 'Inicializa los grupos de roles (Administrador, Supervisor, Vendedor, Cliente), asigna permisos y sincroniza usuarios'

    def handle(self, *args, **options):
        self.stdout.write('Iniciando configuración de Roles y Permisos (RBAC)...')
        setup_roles_and_permissions(stdout=self.stdout)
        sincronizar_usuarios_existentes(stdout=self.stdout)
        self.stdout.write(self.style.SUCCESS('Configuración de Roles (RBAC) finalizada exitosamente.'))
