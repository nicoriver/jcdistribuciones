from decimal import Decimal, ROUND_HALF_UP
from django.db.models import Sum, Count, Q
from comprobantes.models import Remito, DetalleRemito
from clientes.models import Vendedor, Cliente, Zona


class LogisticaService:
    """
    Servicio de dominio para consolidar planillas de carga de depósito,
    hojas de ruta de entrega por chofer y reportes comerciales de ventas.
    """

    @classmethod
    def obtener_remitos_para_reparto(cls, dia_semana=None, zona_id=None, fecha=None):
        """
        Retorna los remitos emitidos filtrados por día de reparto, zona y/o fecha.
        """
        qs = Remito.objects.filter(estado__in=['EMITIDO', 'ENTREGADO'])

        if zona_id and str(zona_id).isdigit():
            qs = qs.filter(cliente__zona_id=int(zona_id))

        if dia_semana and str(dia_semana).isdigit():
            qs = qs.filter(cliente__dia_reparto=int(dia_semana))

        if fecha:
            qs = qs.filter(fecha_emision__date=fecha)

        return qs.select_related(
            'cliente', 'cliente__localidad', 'cliente__localidad__provincia', 'cliente__zona', 'vendedor', 'pedido'
        ).prefetch_related('items').order_by('cliente__razon_social', 'cliente__domicilio')

    @classmethod
    def generar_planilla_carga(cls, remitos_qs):
        """
        Consolida los renglones de remitos totalizando productos y presentaciones.
        Retorna lista de dicts: [{'codigo': ..., 'descripcion': ..., 'presentacion': ..., 'cantidad': ..., 'unidades_base': ...}]
        """
        consolidado = {}

        for remito in remitos_qs:
            for item in remito.items.all():
                key = (item.codigo_historico, item.descripcion_historica, item.presentacion_nombre or 'Unidad')
                if key not in consolidado:
                    consolidado[key] = {
                        'codigo': item.codigo_historico,
                        'descripcion': item.descripcion_historica,
                        'presentacion': item.presentacion_nombre or 'Unidad',
                        'cantidad': Decimal('0.00'),
                        'unidades_base': Decimal('0.00')
                    }

                cant = item.cantidad or Decimal('0.00')
                factor = item.factor_unidades or Decimal('1.00')

                consolidado[key]['cantidad'] += cant
                consolidado[key]['unidades_base'] += (cant * factor)

        resultado = list(consolidado.values())
        resultado.sort(key=lambda x: (x['codigo'], x['descripcion']))
        return resultado

    @classmethod
    def obtener_resumen_ventas_vendedor(cls, fecha_desde=None, fecha_hasta=None):
        """
        Calcula el resumen de facturación y comisión estimada por vendedor en un rango de fechas.
        """
        vendedores = Vendedor.objects.filter(activo=True)
        resumen = []

        for v in vendedores:
            remitos_qs = Remito.objects.filter(vendedor=v, estado__in=['EMITIDO', 'ENTREGADO'])

            if fecha_desde:
                remitos_qs = remitos_qs.filter(fecha_emision__date__gte=fecha_desde)
            if fecha_hasta:
                remitos_qs = remitos_qs.filter(fecha_emision__date__lte=fecha_hasta)

            cant_comprobantes = remitos_qs.count()
            total_facturado = sum(r.monto_total for r in remitos_qs) or Decimal('0.00')
            comision_porc = v.comision_porcentaje or Decimal('0.00')
            comision_estimada = (total_facturado * (comision_porc / Decimal('100.00'))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

            resumen.append({
                'vendedor': v,
                'cant_comprobantes': cant_comprobantes,
                'total_facturado': total_facturado,
                'comision_porcentaje': comision_porc,
                'comision_estimada': comision_estimada
            })

        resumen.sort(key=lambda x: x['total_facturado'], reverse=True)
        return resumen
