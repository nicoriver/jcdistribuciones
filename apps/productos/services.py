from decimal import Decimal, ROUND_HALF_UP


class CalculadoraPreciosService:
    """
    Servicio de cálculo financiero y formación de precios para JC Distribuciones.
    Aplica la fórmula canónica de recargo, IVA y descuento comercial.
    """

    @staticmethod
    def calcular_precio_final(costo, recargo_porc=Decimal('0.00'), iva_porc=Decimal('21.00'), descuento_porc=Decimal('0.00')):
        """
        Calcula el precio final de venta aplicando:
        1. P_recargo = Costo * (1 + Recargo / 100)
        2. P_iva     = P_recargo * (1 + IVA / 100)
        3. P_final   = P_iva * (1 - Descuento / 100)
        Retorna un Decimal redondeado a 2 posiciones con ROUND_HALF_UP.
        """
        c = Decimal(str(costo))
        r = Decimal(str(recargo_porc))
        i = Decimal(str(iva_porc))
        d = Decimal(str(descuento_porc))

        # 1. Aplicar margen / recargo sobre el costo base
        precio_recargo = c * (Decimal('1.00') + (r / Decimal('100.00')))

        # 2. Aplicar alícuota de IVA
        precio_iva = precio_recargo * (Decimal('1.00') + (i / Decimal('100.00')))

        # 3. Aplicar descuento comercial sobre el total
        precio_final = precio_iva * (Decimal('1.00') - (d / Decimal('100.00')))

        return precio_final.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    @classmethod
    def actualizar_precios_producto(cls, producto):
        """
        Recalcula los precios netos gravados y precios finales de todas las listas
        asociadas a un producto al modificarse su costo base o alícuota de IVA.
        """
        costo = producto.costo_base or Decimal('0.00')
        iva = producto.alicuota_iva or Decimal('21.00')

        precios_qs = producto.precios.all()
        actualizados = 0

        for precio in precios_qs:
            recargo = precio.porcentaje_recargo or Decimal('0.00')
            descuento = precio.porcentaje_descuento or Decimal('0.00')

            # Precio neto gravado (sin IVA): costo * (1 + recargo / 100)
            precio_neto = costo * (Decimal('1.00') + (recargo / Decimal('100.00')))
            precio.precio_neto = precio_neto.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

            # Precio final con IVA y descuento comercial
            precio.precio_final = cls.calcular_precio_final(costo, recargo, iva, descuento)
            precio.save(update_fields=['precio_neto', 'precio_final', 'actualizado_en'])
            actualizados += 1

        return actualizados
