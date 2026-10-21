from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.db.models import Q


class DualAuthBackend(ModelBackend):
    """
    Backend de autenticación que permite iniciar sesión ingresando
    indistintamente CUIT/DNI, username o email junto a la contraseña.
    Acepta CUIT con o sin guiones y realiza matching seguro con hash de Django (PBKDF2).
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        UserModel = get_user_model()
        if username is None:
            username = kwargs.get(UserModel.USERNAME_FIELD)
        if not username or not password:
            return None

        identificador = str(username).strip()
        identificador_clean = identificador.replace('-', '').replace('.', '')

        filtros = Q(username__iexact=identificador) | Q(email__iexact=identificador)
        if identificador_clean:
            filtros |= Q(cuit_dni=identificador_clean)
        filtros |= Q(cuit_dni=identificador)

        try:
            usuarios = UserModel.objects.filter(filtros).distinct()
            for user in usuarios:
                if user.check_password(password) and self.user_can_authenticate(user):
                    return user
        except Exception:
            return None

        return None
