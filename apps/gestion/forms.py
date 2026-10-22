from decimal import Decimal
from django import forms
from django.db import transaction
from django.db.models import Q
from django.utils.crypto import get_random_string

from clientes.models import Cliente, Vendedor, AsignacionZonaVendedor, CondicionIVA
from geografia.models import Zona, Localidad
from productos.models import (
    Producto,
    PrecioProducto,
    TipoListaPrecio,
    Categoria,
    Marca,
    AlicuotaIVA,
    IVA_CHOICES
)
from usuarios.models import Usuario


class ClienteForm(forms.ModelForm):
    crear_usuario_portal = forms.BooleanField(
        required=False,
        initial=False,
        label="Habilitar usuario de acceso al portal comercial",
        help_text="Crea una cuenta para que el cliente ingrese al portal mayorista",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    password_portal = forms.CharField(
        required=False,
        label="Contraseña del Portal",
        help_text="Opcional. Si se deja en blanco se generará una contraseña temporal que se mostrará al guardar.",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Dejar en blanco para autogenerar'
        })
    )

    class Meta:
        model = Cliente
        fields = [
            'razon_social', 'nombre_fantasia', 'cuit', 'condicion_iva',
            'domicilio', 'localidad', 'zona', 'vendedor', 'dia_reparto',
            'tipo_lista_precio', 'telefono', 'telefono_alt', 'email', 'contacto',
            'monto_minimo_pedido', 'estado'
        ]
        widgets = {
            'razon_social': forms.TextInput(attrs={'class': 'form-control'}),
            'nombre_fantasia': forms.TextInput(attrs={'class': 'form-control'}),
            'cuit': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '30123456789'}),
            'condicion_iva': forms.Select(attrs={'class': 'form-select'}),
            'domicilio': forms.TextInput(attrs={'class': 'form-control'}),
            'localidad': forms.Select(attrs={'class': 'form-select'}),
            'zona': forms.Select(attrs={'class': 'form-select'}),
            'vendedor': forms.Select(attrs={'class': 'form-select'}),
            'dia_reparto': forms.Select(attrs={'class': 'form-select'}),
            'tipo_lista_precio': forms.Select(attrs={'class': 'form-select'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control'}),
            'telefono_alt': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'contacto': forms.TextInput(attrs={'class': 'form-control'}),
            'monto_minimo_pedido': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'estado': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['tipo_lista_precio'].label = "Lista de Precios"
        self.fields['monto_minimo_pedido'].required = False
        self.password_generada = None
        self.usuario_creado = False

        if self.instance and self.instance.pk and self.instance.usuario:
            self.fields['crear_usuario_portal'].initial = True
            self.fields['crear_usuario_portal'].help_text = (
                f"Usuario actual vinculado: {self.instance.usuario.username} ({self.instance.usuario.email or 'sin email'})"
            )
            self.fields['password_portal'].help_text = (
                "Opcional. Ingrese una nueva contraseña solo si desea cambiar la actual del usuario del portal."
            )

    def clean_monto_minimo_pedido(self):
        monto = self.cleaned_data.get('monto_minimo_pedido')
        if monto is None:
            return Decimal('0.00')
        return monto

    def clean_cuit(self):
        cuit = self.cleaned_data.get('cuit', '').strip().replace('-', '').replace('.', '')
        if not cuit:
            raise forms.ValidationError("El CUIT es obligatorio.")
        if not cuit.isdigit():
            raise forms.ValidationError("El CUIT debe contener únicamente números.")
        if len(cuit) < 10 or len(cuit) > 11:
            raise forms.ValidationError("El CUIT debe tener entre 10 y 11 dígitos numéricos.")

        qs = Cliente.objects.filter(cuit=cuit)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Ya existe un cliente registrado con este CUIT.")

        return cuit

    def clean(self):
        cleaned_data = super().clean()
        crear_usuario = cleaned_data.get('crear_usuario_portal')
        cuit = cleaned_data.get('cuit')
        email = (cleaned_data.get('email') or '').strip()
        pwd = (cleaned_data.get('password_portal') or '').strip()

        # Si el cliente ya tiene usuario vinculado
        if self.instance and self.instance.pk and self.instance.usuario:
            if pwd and len(pwd) < 6:
                self.add_error('password_portal', "La nueva contraseña debe tener al menos 6 caracteres.")
            return cleaned_data

        if crear_usuario:
            if not cuit:
                self.add_error('crear_usuario_portal', "Se requiere un CUIT válido para habilitar el usuario del portal.")
            else:
                # 1. Validar colisión de username en Usuario (no vincular existentes automáticamente)
                if Usuario.objects.filter(username=cuit).exists():
                    self.add_error(
                        'crear_usuario_portal',
                        f"Ya existe un usuario en el sistema con el identificador / username '{cuit}'."
                    )
                # 2. Validar colisión de CUIT / DNI en Usuario
                elif Usuario.objects.filter(cuit_dni=cuit).exists():
                    self.add_error(
                        'crear_usuario_portal',
                        f"Ya existe un usuario en el sistema con el CUIT/DNI '{cuit}'."
                    )

            # 3. Validar colisión de email si se especificó
            if email:
                if Usuario.objects.filter(email__iexact=email).exists():
                    self.add_error(
                        'email',
                        f"El correo electrónico '{email}' ya se encuentra registrado por otro usuario."
                    )

            # 4. Validar contraseña si se ingresó
            if pwd and len(pwd) < 6:
                self.add_error('password_portal', "La contraseña personalizada debe tener al menos 6 caracteres.")

        return cleaned_data

    def save(self, commit=True):
        cliente = super().save(commit=False)
        cuit_clean = self.cleaned_data['cuit']
        cliente.cuit = cuit_clean

        crear_usuario = self.cleaned_data.get('crear_usuario_portal', False)
        pwd = (self.cleaned_data.get('password_portal') or '').strip()
        email_val = (self.cleaned_data.get('email') or '').strip() or None

        self.password_generada = None
        self.usuario_creado = False

        if commit:
            with transaction.atomic():
                # Caso A: Crear nuevo usuario para cliente sin usuario
                if crear_usuario and not cliente.usuario:
                    if not pwd:
                        pwd = get_random_string(10)
                        self.password_generada = pwd
                    else:
                        self.password_generada = None

                    user = Usuario.objects.create_user(
                        username=cuit_clean,
                        cuit_dni=cuit_clean,
                        email=email_val,
                        password=pwd,
                        nombre=self.cleaned_data.get('razon_social', ''),
                        rol='CLIENTE'
                    )
                    cliente.usuario = user
                    self.usuario_creado = True

                # Caso B: Modificar contraseña de usuario existente si fue provista
                elif cliente.usuario and pwd:
                    cliente.usuario.set_password(pwd)
                    cliente.usuario.save(update_fields=['password'])

                cliente.save()

        return cliente


class ProductoForm(forms.ModelForm):
    class Meta:
        model = Producto
        fields = [
            'codigo', 'codigo_barras', 'nombre', 'descripcion',
            'categoria', 'marca', 'alicuota_iva', 'costo_base',
            'punto_reposicion', 'controla_stock', 'activo'
        ]
        widgets = {
            'codigo': forms.TextInput(attrs={'class': 'form-control'}),
            'codigo_barras': forms.TextInput(attrs={'class': 'form-control'}),
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'categoria': forms.Select(attrs={'class': 'form-select'}),
            'marca': forms.Select(attrs={'class': 'form-select'}),
            'alicuota_iva': forms.Select(attrs={'class': 'form-select'}),
            'costo_base': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'punto_reposicion': forms.NumberInput(attrs={'class': 'form-control', 'step': '1'}),
            'controla_stock': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        # Mapear parámetros retrocompatibles si provienen de POST antiguo
        data = kwargs.get('data')
        if data:
            data = data.copy()
            if 'costo' in data and 'costo_base' not in data:
                data['costo_base'] = data['costo']
            if 'codigo_barra' in data and 'codigo_barras' not in data:
                data['codigo_barras'] = data['codigo_barra']
            if 'alicuota_iva' in data:
                val = str(data.get('alicuota_iva')).strip()
                if val.isdigit():
                    alicuota_obj = AlicuotaIVA.objects.filter(id=int(val)).first()
                    if alicuota_obj:
                        data['alicuota_iva'] = str(alicuota_obj.porcentaje)
            kwargs['data'] = data

        super().__init__(*args, **kwargs)
        self.fields['codigo_barras'].required = False
        self.fields['descripcion'].required = False

        # Si estamos editando, mostrar stock actual informativo sin permitir alteración directa
        if self.instance and self.instance.pk:
            self.fields['stock_actual_info'] = forms.IntegerField(
                required=False,
                initial=self.instance.stock_actual,
                disabled=True,
                label="Stock Actual (Kardex)",
                help_text="Inmutable desde edición comercial. Se gestiona exclusivamente mediante Kardex/Movimientos de Stock.",
                widget=forms.NumberInput(attrs={'class': 'form-control bg-light', 'readonly': 'readonly'})
            )

    def clean_codigo(self):
        codigo = self.cleaned_data.get('codigo', '').strip()
        if not codigo:
            raise forms.ValidationError("El código interno es obligatorio.")

        qs = Producto.objects.filter(codigo__iexact=codigo)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError(f"Ya existe un producto con el código '{codigo}'.")

        return codigo

    def save(self, commit=True):
        producto = super().save(commit=False)

        if self.instance and self.instance.pk:
            # Edición comercial: actualizar ÚNICAMENTE campos comerciales permitidos
            # NUNCA leer ni sobreescribir stock_actual para proteger movimientos concurrentes del Kardex
            campos_comerciales = [
                'codigo', 'codigo_barras', 'nombre', 'descripcion',
                'categoria', 'marca', 'alicuota_iva', 'costo_base',
                'punto_reposicion', 'controla_stock', 'activo'
            ]
            if commit:
                producto.save(update_fields=campos_comerciales)
        else:
            # Alta de nuevo producto: asegurar stock inicial en cero
            if producto.stock_actual is None:
                producto.stock_actual = 0
            if commit:
                producto.save()

        return producto


class ZonaForm(forms.ModelForm):
    class Meta:
        model = Zona
        fields = ['nombre', 'descripcion', 'dia_reparto_defecto', 'activa']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. Zona Centro / Litoral'}),
            'descripcion': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Descripción de la cobertura...'}),
            'dia_reparto_defecto': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. Lunes y Jueves'}),
            'activa': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_nombre(self):
        nombre = self.cleaned_data.get('nombre', '').strip()
        if not nombre:
            raise forms.ValidationError("El nombre de la zona es obligatorio.")

        qs = Zona.objects.filter(nombre__iexact=nombre)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError(f"Ya existe una zona registrada con el nombre '{nombre}'.")

        return nombre


class VendedorForm(forms.ModelForm):
    zonas = forms.ModelMultipleChoiceField(
        queryset=Zona.objects.all(),
        required=False,
        label="Zonas de Reparto Asignadas",
        help_text="Seleccione las zonas asignadas operativamente a este vendedor.",
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'})
    )

    class Meta:
        model = Vendedor
        fields = [
            'legajo', 'nombre', 'apellido', 'dni', 'telefono',
            'comision_porcentaje', 'activo', 'usuario'
        ]
        widgets = {
            'legajo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. VEND-001'}),
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'apellido': forms.TextInput(attrs={'class': 'form-control'}),
            'dni': forms.TextInput(attrs={'class': 'form-control'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control'}),
            'comision_porcentaje': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'usuario': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Limitar estrictamente a usuarios con rol 'VENDEDOR' que no estén asignados a otro vendedor
        user_qs = Usuario.objects.filter(rol='VENDEDOR').filter(
            Q(perfil_vendedor__isnull=True)
        )
        if self.instance and self.instance.pk and self.instance.usuario:
            user_qs = (user_qs | Usuario.objects.filter(pk=self.instance.usuario_id))
        self.fields['usuario'].queryset = user_qs.order_by('username')
        self.fields['usuario'].required = False
        self.fields['usuario'].help_text = "Solo se permiten cuentas de usuario con rol 'Vendedor'."
        self.fields['usuario'].error_messages['invalid_choice'] = (
            "Solo se pueden vincular cuentas de usuario con rol 'Vendedor'."
        )

        # Preseleccionar zonas actualmente activas
        if self.instance and self.instance.pk:
            self.fields['zonas'].initial = self.instance.zonas.filter(
                asignaciones_vendedor__activo=True
            )

    def clean_usuario(self):
        usuario = self.cleaned_data.get('usuario')
        if usuario:
            if usuario.rol != 'VENDEDOR':
                raise forms.ValidationError(
                    f"El usuario '{usuario.username}' tiene rol '{usuario.get_rol_display()}'. "
                    "Solo se pueden vincular cuentas de usuario con rol 'Vendedor'."
                )
            if hasattr(usuario, 'perfil_vendedor') and usuario.perfil_vendedor != self.instance:
                raise forms.ValidationError(
                    f"El usuario '{usuario.username}' ya está asignado al vendedor '{usuario.perfil_vendedor.nombre_completo()}'."
                )
        return usuario

    def clean_legajo(self):
        legajo = self.cleaned_data.get('legajo')
        if legajo:
            legajo = legajo.strip()
            qs = Vendedor.objects.filter(legajo__iexact=legajo)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError(f"Ya existe un vendedor con el legajo '{legajo}'.")
        return legajo or None

    def save(self, commit=True):
        vendedor = super().save(commit=commit)

        # Sincronizar asignaciones de zona mediante el modelo histórico vigente
        zonas_seleccionadas = list(self.cleaned_data.get('zonas', []))

        # 1. Asignar o reactivar seleccionadas
        for z in zonas_seleccionadas:
            AsignacionZonaVendedor.objects.update_or_create(
                vendedor=vendedor,
                zona=z,
                defaults={'activo': True}
            )

        # 2. Desactivar las desmarcadas sin borrarlas para preservar histórico
        AsignacionZonaVendedor.objects.filter(
            vendedor=vendedor
        ).exclude(zona__in=zonas_seleccionadas).update(activo=False)

        return vendedor

    def clean_legajo(self):
        legajo = self.cleaned_data.get('legajo')
        if legajo:
            legajo = legajo.strip()
            qs = Vendedor.objects.filter(legajo__iexact=legajo)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError(f"Ya existe un vendedor con el legajo '{legajo}'.")
        return legajo or None

    def save(self, commit=True):
        vendedor = super().save(commit=commit)

        # Sincronizar asignaciones de zona mediante el modelo histórico vigente
        zonas_seleccionadas = list(self.cleaned_data.get('zonas', []))

        # 1. Asignar o reactivar seleccionadas
        for z in zonas_seleccionadas:
            AsignacionZonaVendedor.objects.update_or_create(
                vendedor=vendedor,
                zona=z,
                defaults={'activo': True}
            )

        # 2. Desactivar las desmarcadas sin borrarlas para preservar histórico
        AsignacionZonaVendedor.objects.filter(
            vendedor=vendedor
        ).exclude(zona__in=zonas_seleccionadas).update(activo=False)

        return vendedor


class PrecioProductoForm(forms.ModelForm):
    class Meta:
        model = PrecioProducto
        fields = ['tipo_lista', 'porcentaje_recargo', 'porcentaje_descuento']
        widgets = {
            'tipo_lista': forms.Select(attrs={'class': 'form-select'}),
            'porcentaje_recargo': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'porcentaje_descuento': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }


class ListaPrecioForm(forms.ModelForm):
    class Meta:
        model = TipoListaPrecio
        fields = ['nombre', 'descripcion', 'activa']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. Lista Mayorista'}),
            'descripcion': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Descripción breve...'}),
            'activa': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
