import django.db.models.deletion
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('clientes', '0003_remove_cliente_lista_precio_default'),
        ('comprobantes', '0002_alter_remito_pedido'),
        ('pedidos', '0002_alter_pedido_lista_precio'),
        ('productos', '0004_alter_precioproducto_porcentaje_recargo'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PuntoVentaNumerador',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('punto_venta', models.PositiveIntegerField(default=1, verbose_name='Punto de Venta')),
                ('tipo_documento', models.CharField(choices=[('REMITO', 'Remito Comercial A4'), ('NC', 'Nota de Crédito por Devolución'), ('NCF', 'Nota de Crédito por Faltante')], max_length=20, verbose_name='Tipo de Documento')),
                ('ultimo_numero', models.PositiveIntegerField(default=0, verbose_name='Último Número Emitido')),
            ],
            options={
                'verbose_name': 'Numerador de Punto de Venta',
                'verbose_name_plural': 'Numeradores de Puntos de Venta',
                'ordering': ['punto_venta', 'tipo_documento'],
                'unique_together': {('punto_venta', 'tipo_documento')},
            },
        ),
        migrations.RenameField(
            model_name='remito',
            old_name='numero_remito',
            new_name='numero_completo',
        ),
        migrations.RenameField(
            model_name='remito',
            old_name='emitido_por',
            new_name='supervisor',
        ),
        migrations.RenameField(
            model_name='detalleremito',
            old_name='precio_unitario',
            new_name='precio_unitario_historico',
        ),
        migrations.RenameField(
            model_name='detalleremito',
            old_name='descuento_porcentaje',
            new_name='porcentaje_descuento',
        ),
        migrations.RenameField(
            model_name='detalleremito',
            old_name='total_linea',
            new_name='subtotal',
        ),
        migrations.AddField(
            model_name='remito',
            name='punto_venta',
            field=models.PositiveIntegerField(default=1, verbose_name='Punto de Venta'),
        ),
        migrations.AddField(
            model_name='remito',
            name='numero',
            field=models.PositiveIntegerField(default=1, verbose_name='Número Correlativo'),
        ),
        migrations.AddField(
            model_name='remito',
            name='pedido_origen_id',
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name='ID Pedido de Origen'),
        ),
        migrations.AddField(
            model_name='remito',
            name='subtotal_bruto',
            field=models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=14, verbose_name='Subtotal Bruto'),
        ),
        migrations.AddField(
            model_name='remito',
            name='total_descuento',
            field=models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=14, verbose_name='Total Descuento'),
        ),
        migrations.AddField(
            model_name='remito',
            name='anulado',
            field=models.BooleanField(default=False, verbose_name='Anulado'),
        ),
        migrations.AddField(
            model_name='detalleremito',
            name='presentacion',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='productos.presentacion', verbose_name='Presentación'),
        ),
        migrations.AddField(
            model_name='notacreditointerna',
            name='punto_venta',
            field=models.PositiveIntegerField(default=1, verbose_name='Punto de Venta'),
        ),
        migrations.AddField(
            model_name='notacreditointerna',
            name='numero',
            field=models.PositiveIntegerField(default=1, verbose_name='Número Correlativo'),
        ),
    ]
