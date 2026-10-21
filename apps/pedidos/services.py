from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction
from django.core.exceptions import ValidationError, PermissionDenied
from django.utils import timezone
from .models import Pedido, DetallePedido
from productos.models import PrecioProducto


class PedidoService:
    """
    Servicio de dominio para la gestión del circuito de Pedidos de Venta y Preventa:
    BORRADOR -> PENDIENTE_REVISION -> APROBADO -> FACTURADO_REMITO (o RECHAZADO).
    """

    @classmethod
    def crear_o_recuperar_borrador(cls, cliente):
        """
        Retorna el pedido en estado BORRADOR actual del cliente o crea uno nuevo.
        """
        pedido = Pedido.objects.filter(cliente=cliente, estado='BORRADOR').first()
        if pedido:
            return pedido

        lista_precio = cliente.tipo_lista_precio
        if not lista_precio:
            raise ValidationError(f"El cliente {cliente.razon_social} no tiene una lista de precios asignada.")

        pedido = Pedido.objects.create(
            cliente=cliente,
            vendedor=cliente.vendedor,
            lista_precio=lista_precio,
            estado='BORRADOR'
        )
        return pedido

    @classmethod
    def agregar_item(cls, pedido, producto, presentacion=None, cantidad=1, descuento_extra=Decimal('0.00'), precio_unitario=None):
        """
        Agrega o actualiza un producto en un pedido en borrador congelando los precios históricos.
        """
        if pedido.estado != 'BORRADOR':
            raise ValidationError("No se pueden modificar productos en un pedido que no esté en estado Borrador.")

        factor = int(presentacion.factor_conversion) if presentacion else 1
        cant_int = int(Decimal(str(cantidad)))
        if cant_int <= 0:
            raise ValidationError("La cantidad debe ser mayor a cero.")

        unidades_solicitadas = cant_int * factor
        supera_stock = (unidades_solicitadas > producto.stock_actual) if producto.controla_stock else False

        if hasattr(producto.alicuota_iva, 'porcentaje'):
            alicuota_iva = producto.alicuota_iva.porcentaje
        elif producto.alicuota_iva is not None:
            alicuota_iva = Decimal(str(producto.alicuota_iva))
        else:
            alicuota_iva = Decimal('21.00')

        precio_obj = None
        if pedido.lista_precio_id:
            precio_obj = PrecioProducto.objects.filter(tipo_lista=pedido.lista_precio, producto=producto).first()
        if not precio_obj and getattr(pedido.cliente, 'tipo_lista_precio', None):
            precio_obj = PrecioProducto.objects.filter(tipo_lista=pedido.cliente.tipo_lista_precio, producto=producto).first()

        if precio_unitario is not None:
            p_unitario = Decimal(str(precio_unitario)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            p_neto = (p_unitario / (Decimal('1.00') + alicuota_iva / Decimal('100.00'))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            descuento_final = Decimal(str(descuento_extra or '0.00'))
        elif precio_obj:
            p_neto = precio_obj.precio_neto.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            p_unitario = precio_obj.precio_final.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            descuento_final = Decimal(str(descuento_extra)) if Decimal(str(descuento_extra)) > Decimal('0.00') else Decimal('0.00')
        else:
            raise ValidationError(f"No existe precio configurado para el producto '{producto.nombre}'.")

        item = DetallePedido.objects.filter(
            pedido=pedido,
            producto=producto,
            presentacion=presentacion
        ).first()

        if item:
            item.cantidad += cant_int
            item.factor_unidades = factor
            item.supera_stock_disponible = supera_stock
            item.porcentaje_descuento = descuento_final
            item.calcular_linea(save=True)
        else:
            item = DetallePedido.objects.create(
                pedido=pedido,
                producto=producto,
                presentacion=presentacion,
                cantidad=cant_int,
                factor_unidades=factor,
                codigo_producto_historico=producto.codigo,
                nombre_producto_historico=producto.nombre,
                precio_unitario=p_unitario,
                precio_unitario_neto=p_neto,
                porcentaje_iva=alicuota_iva,
                porcentaje_descuento=descuento_final,
                supera_stock_disponible=supera_stock
            )
            item.calcular_linea(save=True)

        pedido.recalcular_totales(save=True)
        return item

    @classmethod
    @transaction.atomic
    def enviar_a_revision(cls, pedido, observaciones=None):
        """
        Transiciona un pedido de BORRADOR a PENDIENTE_REVISION validando ítems y monto mínimo.
        """
        if pedido.estado != 'BORRADOR':
            raise ValidationError("Solo se pueden enviar a revisión pedidos que estén en estado Borrador.")

        if pedido.detalles.count() == 0:
            raise ValidationError("El pedido no contiene ningún producto.")

        pedido.recalcular_totales(save=True)

        monto_minimo = getattr(pedido.cliente, 'monto_minimo_pedido', None) or Decimal('0.00')
        if pedido.total_estimado < monto_minimo:
            raise ValidationError(
                f"El total del pedido (${pedido.total_estimado}) no alcanza el monto mínimo requerido (${monto_minimo})."
            )

        if observaciones is not None:
            pedido.observaciones = observaciones

        pedido.fecha_envio = timezone.now()
        pedido.estado = 'PENDIENTE_REVISION'
        pedido.save(update_fields=['observaciones', 'fecha_envio', 'estado', 'total_estimado'])
        return pedido

    @classmethod
    def enviar_pedido(cls, pedido, observaciones=None):
        """Alias compatible con llamadas previas."""
        return cls.enviar_a_revision(pedido, observaciones=observaciones)

    @classmethod
    @transaction.atomic
    def aprobar_pedido(cls, pedido, usuario=None, descuentos_por_renglon=None):
        """
        Aprueba un pedido (permitiendo al vendedor ajustar descuentos por renglón si se indican)
        y lo deja en estado APROBADO listo para ser facturado por el Supervisor.
        """
        if pedido.estado not in ['BORRADOR', 'PENDIENTE_REVISION', 'ENVIADO', 'EN_REVISION']:
            raise ValidationError(f"No se puede aprobar un pedido en estado '{pedido.get_estado_display()}'.")

        if pedido.detalles.count() == 0:
            raise ValidationError("No se puede aprobar un pedido sin renglones.")

        if descuentos_por_renglon and isinstance(descuentos_por_renglon, dict):
            for detalle_id, nuevo_desc in descuentos_por_renglon.items():
                det = pedido.detalles.filter(id=detalle_id).first()
                if det:
                    det.porcentaje_descuento = Decimal(str(nuevo_desc))
                    det.calcular_linea(save=True)

        pedido.recalcular_totales(save=False)
        pedido.estado = 'APROBADO'
        pedido.aprobado_por = usuario
        pedido.fecha_aprobacion = timezone.now()
        if not pedido.fecha_envio:
            pedido.fecha_envio = pedido.fecha_aprobacion
        pedido.save()
        return pedido

    @classmethod
    @transaction.atomic
    def rechazar_pedido(cls, pedido, motivo="", usuario=None):
        """
        Rechaza un pedido registrando el motivo de rechazo.
        """
        if not motivo or not str(motivo).strip():
            raise ValidationError("Debe especificar un motivo de rechazo.")

        if pedido.estado in ['FACTURADO_REMITO', 'FACTURADO']:
            raise ValidationError("No se puede rechazar un pedido que ya fue facturado en remito.")

        pedido.estado = 'RECHAZADO'
        pedido.motivo_rechazo = str(motivo).strip()
        pedido.save(update_fields=['estado', 'motivo_rechazo'])
        return pedido

    @classmethod
    @transaction.atomic
    def facturar_pedido_a_remito(cls, pedido, supervisor, punto_venta=1):
        """
        Ejecutado dentro de @transaction.atomic:
        1. Bloquea el pedido con select_for_update() para evitar doble facturación.
        2. Verifica que el pedido esté en estado APROBADO.
        3. Toma los renglones aprobados del pedido y llama a RemitoService.emitir_remito.
        4. Marca el pedido como FACTURADO_REMITO y asocia el ID del remito generado.
        5. Retorna la instancia de Remito generada.
        """
        from comprobantes.services import RemitoService

        if isinstance(pedido, (int, str)):
            pedido_obj = Pedido.objects.select_for_update().get(id=pedido)
        else:
            pedido_obj = Pedido.objects.select_for_update().get(id=pedido.id)

        if pedido_obj.estado in ['FACTURADO_REMITO', 'FACTURADO'] or pedido_obj.remito_asociado_id:
            raise ValidationError("Este pedido ya fue facturado anteriormente. No se permite la doble facturación.")

        if pedido_obj.estado != 'APROBADO':
            raise ValidationError(
                f"Solo se pueden facturar pedidos en estado APROBADO (estado actual: {pedido_obj.get_estado_display()})."
            )

        detalles_qs = pedido_obj.detalles.select_related('producto', 'presentacion').all()
        if not detalles_qs.exists():
            raise ValidationError("El pedido no posee renglones para facturar.")

        items_remito = []
        for det in detalles_qs:
            items_remito.append({
                'detalle_pedido_origen': det,
                'producto': det.producto,
                'presentacion': det.presentacion,
                'presentacion_nombre': det.presentacion.nombre if det.presentacion else 'Unidad',
                'factor_unidades': int(det.factor_unidades or 1),
                'codigo_historico': det.codigo_producto_historico or det.producto.codigo,
                'descripcion_historica': det.nombre_producto_historico or det.producto.nombre,
                'cantidad': int(det.cantidad),
                'precio_unitario_historico': det.precio_unitario,
                'porcentaje_descuento': det.porcentaje_descuento or Decimal('0.00'),
            })

        vendedor = pedido_obj.vendedor or pedido_obj.cliente.vendedor

        remito = RemitoService.emitir_remito(
            cliente=pedido_obj.cliente,
            vendedor=vendedor,
            supervisor=supervisor,
            items=items_remito,
            punto_venta=punto_venta,
            pedido=pedido_obj,
            pedido_origen_id=pedido_obj.id,
            observaciones=pedido_obj.observaciones
        )

        pedido_obj.estado = 'FACTURADO_REMITO'
        pedido_obj.remito_asociado_id = remito.id
        pedido_obj.save(update_fields=['estado', 'remito_asociado_id'])

        return remito

    @classmethod
    def crear_o_recuperar_borrador_vendedor(cls, cliente, vendedor_usuario):
        """
        Recupera o crea un borrador para toma de pedido presencial en calle.
        """
        vendedor_perfil = getattr(vendedor_usuario, 'perfil_vendedor', None)
        if vendedor_usuario.rol == 'VENDEDOR' and not vendedor_usuario.is_superuser:
            if not vendedor_perfil or cliente.vendedor != vendedor_perfil:
                raise PermissionDenied("No tiene permisos para tomar pedidos de un cliente asignado a otro vendedor.")

        return cls.crear_o_recuperar_borrador(cliente)

    @classmethod
    @transaction.atomic
    def confirmar_pedido_preventa(cls, pedido, vendedor_usuario):
        """
        Confirma y aprueba directamente un pedido tomado en la calle por el vendedor.
        """
        return cls.aprobar_pedido(pedido, usuario=vendedor_usuario)
