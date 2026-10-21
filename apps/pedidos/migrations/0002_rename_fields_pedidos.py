from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('pedidos', '0002_alter_pedido_lista_precio'),
    ]

    operations = [
        migrations.RenameField(
            model_name='pedido',
            old_name='monto_total',
            new_name='total_estimado',
        ),
        migrations.RenameField(
            model_name='pedido',
            old_name='observaciones_cliente',
            new_name='observaciones',
        ),
        migrations.RenameField(
            model_name='detallepedido',
            old_name='descuento_porcentaje',
            new_name='porcentaje_descuento',
        ),
        migrations.RenameField(
            model_name='detallepedido',
            old_name='total_linea',
            new_name='subtotal',
        ),
    ]
