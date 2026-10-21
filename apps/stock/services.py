from decimal import Decimal
from django.db import transaction
from productos.models import Producto
from .models import ConfiguracionStock, MovimientoStock


class StockService:
    """
    Servicio de dominio encapsulado para gestionar los movimientos inmutables de inventario y stock.
    """

    @classmethod
    @transaction.atomic
    def registrar_movimiento(cls, producto, cantidad, tipo_movimiento, documento_referencia="", usuario=None, motivo="", observaciones=""):
        """
        Registra un movimiento inmutable en el libro de stock y actualiza existencias en Producto.
        Utiliza select_for_update() para evitar condiciones de carrera concurrentes.
        """
        if isinstance(producto, (int, str)):
            prod_obj = Producto.objects.select_for_update().get(id=producto)
        else:
            prod_obj = Producto.objects.select_for_update().get(id=producto.id)

        cant_int = int(cantidad)
        config = ConfiguracionStock.get_solo()

        stock_anterior = int(prod_obj.stock_actual or 0)

        # Si el control general de stock o el control del producto está deshabilitado
        if not config.control_stock_habilitado or not prod_obj.controla_stock:
            stock_resultante = stock_anterior
        else:
            stock_resultante = stock_anterior + cant_int
            prod_obj.stock_actual = stock_resultante
            prod_obj.save(update_fields=['stock_actual'])

        obs_final = observaciones or motivo

        movimiento = MovimientoStock.objects.create(
            producto=prod_obj,
            tipo_movimiento=tipo_movimiento,
            cantidad=cant_int,
            stock_anterior=stock_anterior,
            stock_resultante=stock_resultante,
            documento_referencia=documento_referencia,
            motivo=motivo or observaciones,
            observaciones=obs_final,
            usuario=usuario
        )

        return movimiento
