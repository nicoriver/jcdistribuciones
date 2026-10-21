import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('clientes', '0002_remove_localidad_provincia_alter_cliente_localidad_and_more'),
        ('productos', '0002_tipolistaprecio_rename_activo_marca_activa_and_more'),
    ]

    operations = [
        migrations.RenameField(
            model_name='cliente',
            old_name='lista_precio_default',
            new_name='tipo_lista_precio',
        ),
        migrations.AlterField(
            model_name='cliente',
            name='tipo_lista_precio',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='clientes',
                to='productos.tipolistaprecio',
                verbose_name='Tipo de Lista de Precios'
            ),
        ),
    ]
