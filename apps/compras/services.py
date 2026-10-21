from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction
from django.core.exceptions import ValidationError
from productos.models import Producto
from productos.services import CalculadoraPreciosService
from stock.services import StockService
from .models import Compra, DetalleCompra


class CompraService:
    """
    Servicio de dominio transaccional para la gestión de Compras y Reposición de Inventario.
    Asegura consistencia atómica:
      1. Registra cabecera y detalles de Compra.
      2. Incrementa el stock_actual del producto (si controla_stock=True).
      3. Actualiza el costo_base del producto.
      4. Recalcula automáticamente todas sus listas de precios asociadas.
      5. Registra el movimiento inmutable en el Kardex de Stock (apps/stock/).
    """

    @classmethod
    @transaction.atomic
    def registrar_compra(cls, proveedor, usuario, nro_comprobante, items, observaciones=""):
        """
        Registra una compra y dispara todas las reglas de negocio asociadas dentro de una transacción atómica.

        Parámetros:
          - proveedor: Instancia de proveedores.Proveedor
          - usuario: Instancia de usuarios.Usuario operador
          - nro_comprobante: str (ej: "FC-0001-00004567")
          - items: list de dicts con:
              [
                  {
                      'producto': Producto o producto_id,
                      'cantidad': int (> 0),
                      'precio_costo_unitario': Decimal (>= 0)
                  },
                  ...
              ]
          - observaciones: str (opcional)

        Retorna:
          Instancia de Compra generada.
        """
        if not proveedor:
            raise ValidationError("Debe especificar un proveedor válido.")

        if not usuario:
            raise ValidationError("Debe especificar el usuario que registra la compra.")

        nro_comp = str(nro_comprobante or '').strip()
        if not nro_comp:
            raise ValidationError("El número de comprobante del proveedor es obligatorio.")

        if not items:
            raise ValidationError("La compra debe contener al menos un producto.")

        # 1. Crear cabecera de Compra
        compra = Compra.objects.create(
            proveedor=proveedor,
            usuario=usuario,
            nro_comprobante_proveedor=nro_comp,
            total_compra=Decimal('0.00'),
            observaciones=observaciones or ''
        )

        total_acumulado = Decimal('0.00')

        # 2. Procesar cada ítem
        for idx, item in enumerate(items, start=1):
            prod_val = item.get('producto')
            if not prod_val:
                raise ValidationError(f"El renglón #{idx} no especifica un producto.")

            if isinstance(prod_val, (int, str)):
                producto_obj = Producto.objects.select_for_update().get(id=prod_val)
            else:
                producto_obj = Producto.objects.select_for_update().get(id=prod_val.id)

            cant_raw = item.get('cantidad')
            try:
                cantidad = int(cant_raw)
            except (ValueError, TypeError):
                raise ValidationError(f"Cantidad inválida en renglón #{idx}: '{cant_raw}'. Debe ser un número entero.")

            if cantidad <= 0:
                raise ValidationError(f"La cantidad del renglón #{idx} ({producto_obj.nombre}) debe ser mayor a 0.")

            costo_raw = item.get('precio_costo_unitario')
            try:
                costo_unitario = Decimal(str(costo_raw)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            except Exception:
                raise ValidationError(f"Precio de costo inválido en renglón #{idx}: '{costo_raw}'.")

            if costo_unitario < Decimal('0.00'):
                raise ValidationError(f"El costo unitario en renglón #{idx} ({producto_obj.nombre}) no puede ser negativo.")

            subtotal = (costo_unitario * cantidad).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            total_acumulado += subtotal

            # Crear detalle de compra
            DetalleCompra.objects.create(
                compra=compra,
                producto=producto_obj,
                cantidad=cantidad,
                precio_costo_unitario=costo_unitario,
                subtotal=subtotal
            )

            # a) Actualizar costo_base en el producto
            producto_obj.costo_base = costo_unitario
            producto_obj.save(update_fields=['costo_base'])

            # b) Recalcular automáticamente todas las listas de precios
            CalculadoraPreciosService.actualizar_precios_producto(producto_obj)

            # c) Incrementar stock y registrar en Kardex inmutable de stock
            documento_ref = f"Compra {compra.nro_comprobante_proveedor}"
            StockService.registrar_movimiento(
                producto=producto_obj,
                cantidad=cantidad,
                tipo_movimiento='ENTRADA_COMPRA',
                documento_referencia=documento_ref,
                usuario=usuario,
                motivo=f"Ingreso por Compra N° {compra.id} ({compra.nro_comprobante_proveedor})",
                observaciones=observaciones or f"Proveedor: {proveedor.razon_social}"
            )

        # 3. Guardar total de la compra
        compra.total_compra = total_acumulado
        compra.save(update_fields=['total_compra'])

        return compra
