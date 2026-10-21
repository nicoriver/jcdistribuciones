from django import forms
from clientes.models import Cliente
from productos.models import Producto, PrecioProducto, ListaPrecio
from usuarios.models import Usuario


class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = [
            'razon_social', 'nombre_fantasia', 'cuit', 'condicion_iva',
            'domicilio', 'localidad', 'zona', 'vendedor', 'dia_reparto',
            'tipo_lista_precio', 'telefono', 'email', 'monto_minimo_pedido', 'estado'
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
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'monto_minimo_pedido': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'estado': forms.Select(attrs={'class': 'form-select'}),
        }

    def save(self, commit=True):
        cliente = super().save(commit=False)
        cuit_clean = self.cleaned_data['cuit'].strip().replace('-', '')
        cliente.cuit = cuit_clean

        # Si el cliente no tiene usuario asignado aún, crear o buscar el Usuario portal correspondiente
        if not hasattr(cliente, 'usuario') or cliente.usuario is None:
            user = Usuario.objects.filter(cuit_dni=cuit_clean).first()
            if not user:
                user = Usuario.objects.filter(username=cuit_clean).first()

            if not user:
                email_val = self.cleaned_data.get('email') or None
                user = Usuario.objects.create_user(
                    username=cuit_clean,
                    cuit=cuit_clean,
                    email=email_val,
                    password=cuit_clean,
                    nombre_completo=self.cleaned_data['razon_social'],
                    rol='CLIENTE'
                )

            cliente.usuario = user

        if commit:
            cliente.save()
        return cliente


class ProductoForm(forms.ModelForm):
    class Meta:
        model = Producto
        fields = [
            'codigo', 'codigo_barras', 'nombre', 'descripcion',
            'categoria', 'marca', 'alicuota_iva', 'costo_base',
            'stock_actual', 'punto_reposicion', 'controla_stock', 'activo'
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
            'stock_actual': forms.NumberInput(attrs={'class': 'form-control', 'step': '1'}),
            'punto_reposicion': forms.NumberInput(attrs={'class': 'form-control', 'step': '1'}),
            'controla_stock': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['codigo_barras'].required = False
        self.fields['descripcion'].required = False
        # Si llega 'costo' por POST antiguo, mapearlo a 'costo_base'
        if self.data and 'costo' in self.data and 'costo_base' not in self.data:
            self.data = self.data.copy()
            self.data['costo_base'] = self.data['costo']
        # Si llega 'alicuota_iva' como id de AlicuotaIVA, mapearlo a su porcentaje
        if self.data and 'alicuota_iva' in self.data:
            val = str(self.data.get('alicuota_iva')).strip()
            if val.isdigit():
                alicuota_obj = AlicuotaIVA.objects.filter(id=int(val)).first()
                if alicuota_obj:
                    self.data = self.data.copy()
                    self.data['alicuota_iva'] = str(alicuota_obj.porcentaje)


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
        model = ListaPrecio
        fields = ['nombre', 'descripcion', 'activa']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. Lista Mayorista'}),
            'descripcion': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Descripción breve...'}),
            'activa': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

