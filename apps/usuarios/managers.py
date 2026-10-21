from django.contrib.auth.base_user import BaseUserManager


class CustomUserManager(BaseUserManager):
    """
    Manager personalizado para el modelo Usuario de JC Distribuciones.
    Soporta creación de usuarios por username, CUIT/DNI o email, garantizando
    retrocompatibilidad y saneamiento de datos.
    """

    def create_user(
        self,
        username=None,
        cuit=None,
        cuit_dni=None,
        email=None,
        password=None,
        nombre='',
        apellido='',
        nombre_completo=None,
        **extra_fields
    ):
        ident_cuit_dni = cuit_dni if cuit_dni is not None else cuit

        if not username and not ident_cuit_dni and not email:
            raise ValueError('Debe especificar al menos un identificador (username, CUIT/DNI o email).')

        if email:
            email = self.normalize_email(email)

        if ident_cuit_dni:
            ident_cuit_dni = str(ident_cuit_dni).strip().replace('-', '').replace('.', '')

        if username:
            username = str(username).strip()

        if nombre_completo and not nombre and not apellido:
            parts = str(nombre_completo).strip().split(' ', 1)
            nombre = parts[0]
            apellido = parts[1] if len(parts) > 1 else ''

        user = self.model(
            username=username,
            cuit_dni=ident_cuit_dni,
            email=email,
            nombre=nombre,
            apellido=apellido,
            **extra_fields
        )

        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()

        user.save(using=self._db)
        return user

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('rol', 'ADMIN')

        if extra_fields.get('is_staff') is not True:
            raise ValueError('El superusuario debe tener is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('El superusuario debe tener is_superuser=True.')

        return self.create_user(
            username=username,
            email=email,
            password=password,
            **extra_fields
        )
