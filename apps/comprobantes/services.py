from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction
from django.core.exceptions import ValidationError
from pedidos.models import Pedido
from productos.models import Producto, Presentacion, PrecioProducto
from stock.services import StockService
from .models import PuntoVentaNumerador, Remito, DetalleRemito, NotaCreditoInterna, DetalleNotaCredito


class RemitoService:
    """
    Servicio Transaccional de Facturación por Remito A4 y Notas de Crédito Internas (NC / NCF).
    - El Remito A4 es el comprobante principal de cobro y despacho.
    - Descuenta existencias físicas exclusivamente en el momento de su emisión.
    - Utiliza cerrojo pesimista select_for_update() sobre PuntoVentaNumerador y Producto.
    """

    @classmethod
    @transaction.atomic
    def emitir_remito(
        cls,
        cliente,
        vendedor=None,
        supervisor=None,
        items=None,
        punto_venta=1,
        pedido_origen_id=None,
        pedido=None,
        observaciones="",
        fecha=None,
        tipo_lista_precio=None,
        **kwargs
    ):
        """
        Emite un Remito A4 de forma transaccional:
        1. Bloquea PuntoVentaNumerador con select_for_update() e incrementa el correlativo sin saltos.
        2. Congela el snapshot histórico inmutable de cada producto en DetalleRemito.
        3. Descuenta el stock físico en unidades base (cantidad * factor_unidades) si controla_stock=True.
        4. Registra el movimiento en MovimientoStock con tipo 'SALIDA_REMITO' y referencia al remito.
        """
        # Soporte flexible de argumentos posicionales/keywords
        if isinstance(vendedor, list) and items is None:
            items = vendedor
            vendedor = kwargs.get('vendedor_obj') or getattr(cliente, 'vendedor', None)

        if items is None:
            items = kwargs.get('items_data') or kwargs.get('detalles') or []

        if supervisor is None:
            supervisor = kwargs.get('usuario') or kwargs.get('usuario_emisor') or kwargs.get('emitido_por')

        if not cliente:
            raise ValidationError("Debe especificar un cliente válido para emitir el remito.")

        # Vendedor: obtenido de la ficha del cliente cuando exista, permitido vacío cuando no exista
        vendedor = getattr(cliente, 'vendedor', None)

        if not supervisor:
            raise ValidationError("El remito requiere el usuario supervisor/operador que lo emite.")

        if not items:
            raise ValidationError("El remito debe contener al menos un ítem.")

        # Normalizar fecha comercial
        fecha_val = fecha or kwargs.get('fecha_comercial')
        if isinstance(fecha_val, str) and fecha_val.strip():
            from datetime import date
            try:
                fecha_val = date.fromisoformat(fecha_val.strip())
            except ValueError:
                raise ValidationError(f"Formato de fecha comercial inválido: '{fecha_val}'.")
        elif hasattr(fecha_val, 'date') and not hasattr(fecha_val, 'year'):
            pass
        elif hasattr(fecha_val, 'date'):
            fecha_val = fecha_val.date()

        if not fecha_val and pedido and getattr(pedido, 'fecha_creacion', None):
            fecha_val = pedido.fecha_creacion.date()

        # Normalizar tipo de lista de precios
        if not tipo_lista_precio:
            tipo_lista_precio = kwargs.get('tipo_lista') or kwargs.get('lista_precio')
            if not tipo_lista_precio and pedido and getattr(pedido, 'tipo_lista_precio', None):
                tipo_lista_precio = pedido.tipo_lista_precio
            elif not tipo_lista_precio and getattr(cliente, 'tipo_lista_precio', None):
                tipo_lista_precio = cliente.tipo_lista_precio

        pv = int(punto_venta or 1)

        # 1. Numeración correlativa segura con select_for_update() sobre PuntoVentaNumerador
        numerador, _ = PuntoVentaNumerador.objects.select_for_update().get_or_create(
            punto_venta=pv,
            tipo_documento='REMITO',
            defaults={'ultimo_numero': 0}
        )
        numerador.ultimo_numero += 1
        numerador.save(update_fields=['ultimo_numero'])

        numero = numerador.ultimo_numero
        numero_completo = f"R-{pv:04d}-{numero:08d}"

        if pedido and not pedido_origen_id:
            pedido_origen_id = pedido.id

        # 2. Crear cabecera del Remito
        remito = Remito.objects.create(
            punto_venta=pv,
            numero=numero,
            numero_completo=numero_completo,
            cliente=cliente,
            vendedor=vendedor,
            supervisor=supervisor,
            pedido=pedido,
            pedido_origen_id=pedido_origen_id,
            fecha=fecha_val,
            tipo_lista_precio=tipo_lista_precio,
            subtotal_bruto=Decimal('0.00'),
            total_descuento=Decimal('0.00'),
            monto_total=Decimal('0.00'),
            observaciones=observaciones or '',
            anulado=False,
            estado='EMITIDO'
        )

        subtotal_bruto_acum = Decimal('0.00')
        total_descuento_acum = Decimal('0.00')
        monto_total_acum = Decimal('0.00')

        # 3. Procesar cada renglón
        for idx, item_info in enumerate(items, start=1):
            prod_input = item_info.get('producto')
            if not prod_input:
                raise ValidationError(f"El renglón #{idx} no especifica un producto.")

            if isinstance(prod_input, (int, str)):
                producto_obj = Producto.objects.select_for_update().get(id=prod_input)
            else:
                producto_obj = Producto.objects.select_for_update().get(id=prod_input.id)

            pres_input = item_info.get('presentacion')
            presentacion_obj = None
            if pres_input:
                if isinstance(pres_input, (int, str)):
                    presentacion_obj = Presentacion.objects.filter(id=pres_input, producto=producto_obj).first()
                else:
                    presentacion_obj = pres_input

            cant_raw = item_info.get('cantidad', 0)
            try:
                cant_dec = Decimal(str(cant_raw))
            except Exception:
                raise ValidationError(f"Cantidad inválida en renglón #{idx}: '{cant_raw}'.")

            if cant_dec <= Decimal('0'):
                raise ValidationError(f"La cantidad del producto '{producto_obj.nombre}' debe ser mayor a 0.")

            if cant_dec % Decimal('1') != Decimal('0'):
                raise ValidationError(
                    f"La cantidad del producto '{producto_obj.nombre}' debe ser un número entero (se ingresó '{cant_raw}'). "
                    "No se permiten cantidades fraccionarias."
                )
            cantidad = int(cant_dec)

            # Factor de unidades base
            if 'factor_unidades' in item_info and item_info['factor_unidades'] is not None:
                factor_unidades = int(Decimal(str(item_info['factor_unidades'])))
            elif presentacion_obj:
                factor_unidades = int(presentacion_obj.factor_conversion or 1)
            else:
                factor_unidades = 1

            if factor_unidades <= 0:
                factor_unidades = 1

            # Resolución y congelamiento estricto del precio unitario
            precio_raw = item_info.get('precio_unitario_historico', item_info.get('precio_unitario'))

            if precio_raw is not None:
                precio_unitario_historico = Decimal(str(precio_raw)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            else:
                if not tipo_lista_precio:
                    raise ValidationError(
                        f"No se pudo resolver el precio del producto '{producto_obj.nombre}' [{producto_obj.codigo}]. "
                        "Debe especificar una lista de precios válida."
                    )

                precio_lista = PrecioProducto.objects.filter(
                    producto=producto_obj,
                    tipo_lista=tipo_lista_precio
                ).first()
                if not precio_lista:
                    raise ValidationError(
                        f"El producto '{producto_obj.nombre}' [{producto_obj.codigo}] no tiene precio definido "
                        f"en la lista '{tipo_lista_precio.nombre}'."
                    )

                precio_base = precio_lista.precio_final
                precio_unitario_historico = (precio_base * Decimal(factor_unidades)).quantize(
                    Decimal('0.01'), rounding=ROUND_HALF_UP
                )

            desc_raw = item_info.get('porcentaje_descuento', item_info.get('descuento_porcentaje', Decimal('0.00')))
            porcentaje_descuento = Decimal(str(desc_raw or '0.00')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            if porcentaje_descuento < Decimal('0.00') or porcentaje_descuento > Decimal('100.00'):
                raise ValidationError(f"El porcentaje de descuento ({porcentaje_descuento}%) debe estar entre 0 y 100.")

            # Cálculos comerciales del renglón
            bruto_linea = (precio_unitario_historico * Decimal(cantidad)).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )
            descuento_linea = (bruto_linea * (porcentaje_descuento / Decimal('100.00'))).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )
            subtotal_linea = (bruto_linea - descuento_linea).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )

            presentacion_nombre = (
                item_info.get('presentacion_nombre')
                or (presentacion_obj.nombre if presentacion_obj else 'Unidad')
            )

            DetalleRemito.objects.create(
                remito=remito,
                detalle_pedido_origen=item_info.get('detalle_pedido_origen'),
                producto=producto_obj,
                presentacion=presentacion_obj,
                presentacion_nombre=presentacion_nombre,
                factor_unidades=factor_unidades,
                codigo_historico=item_info.get('codigo_historico') or producto_obj.codigo,
                descripcion_historica=(item_info.get('descripcion_historica') or producto_obj.nombre)[:150],
                cantidad=cantidad,
                precio_unitario_historico=precio_unitario_historico,
                porcentaje_descuento=porcentaje_descuento,
                subtotal=subtotal_linea,
                cantidad_devuelta=0
            )

            subtotal_bruto_acum += bruto_linea
            total_descuento_acum += descuento_linea
            monto_total_acum += subtotal_linea

            # 4. Descuento de stock en unidades base y registro en Kardex
            unidades_base_egreso = -(cantidad * factor_unidades)
            StockService.registrar_movimiento(
                producto=producto_obj,
                cantidad=unidades_base_egreso,
                tipo_movimiento='SALIDA_REMITO',
                documento_referencia=remito.numero_completo,
                usuario=supervisor,
                motivo=f"Salida por emisión de Remito N° {remito.numero_completo}",
                observaciones=f"Cliente: {cliente.razon_social} | Remito: {remito.numero_completo}"
            )

        # 5. Actualizar totales en cabecera
        remito.subtotal_bruto = subtotal_bruto_acum
        remito.total_descuento = total_descuento_acum
        remito.monto_total = monto_total_acum
        remito.save(update_fields=['subtotal_bruto', 'total_descuento', 'monto_total'])

        return remito

    @classmethod
    @transaction.atomic
    def registrar_nota_credito(
        cls,
        remito,
        items_data,
        motivo_tipo='NC',
        reingresa_stock=None,
        usuario=None,
        observaciones="",
        punto_venta=None
    ):
        """
        Registra una Nota de Crédito Interna asociada a un Remito:
        - 'NCF' (Faltante de despacho): NO reingresa mercadería a stock.
        - 'NC' (Devolución de mercadería): Reingresa mercadería a stock según reingresa_stock (True por defecto).
        Valida estrictamente que no se devuelvan más unidades que las remitidas pendientes.
        """
        if isinstance(remito, (int, str)):
            remito_obj = Remito.objects.select_for_update().get(id=remito)
        else:
            remito_obj = Remito.objects.select_for_update().get(id=remito.id)

        if remito_obj.anulado or remito_obj.estado == 'ANULADO':
            raise ValidationError("No se puede emitir una Nota de Crédito sobre un Remito ANULADO.")

        if motivo_tipo not in ['NC', 'NCF']:
            raise ValidationError("El tipo de Nota de Crédito debe ser 'NC' (Devolución) o 'NCF' (Faltante).")

        if not items_data:
            raise ValidationError("Debe detallar al menos un ítem para la Nota de Crédito.")

        # Regla: NCF nunca reingresa stock; NC reingresa stock salvo que se indique explícitamente False
        if motivo_tipo == 'NCF':
            reingresa_stock_final = False
        else:
            reingresa_stock_final = True if reingresa_stock is None else bool(reingresa_stock)

        pv = int(punto_venta or remito_obj.punto_venta or 1)
        operador = usuario or remito_obj.supervisor

        # Numeración correlativa segura con select_for_update()
        numerador, _ = PuntoVentaNumerador.objects.select_for_update().get_or_create(
            punto_venta=pv,
            tipo_documento=motivo_tipo,
            defaults={'ultimo_numero': 0}
        )
        numerador.ultimo_numero += 1
        numerador.save(update_fields=['ultimo_numero'])

        numero = numerador.ultimo_numero
        numero_nc = f"{motivo_tipo}-{pv:04d}-{numero:08d}"

        nota_credito = NotaCreditoInterna.objects.create(
            punto_venta=pv,
            numero=numero,
            numero_nc=numero_nc,
            remito=remito_obj,
            motivo_tipo=motivo_tipo,
            reingresa_stock=reingresa_stock_final,
            monto_total=Decimal('0.00'),
            observaciones=observaciones or '',
            usuario=operador
        )

        monto_total_nc = Decimal('0.00')
        items_procesados = 0

        for item_info in items_data:
            det_remito_id = item_info.get('detalle_remito_id') or (
                item_info.get('detalle_remito').id if item_info.get('detalle_remito') else None
            )
            prod_input = item_info.get('producto')

            if det_remito_id:
                det_remito = DetalleRemito.objects.select_for_update().get(id=det_remito_id, remito=remito_obj)
            elif prod_input:
                prod_id = prod_input if isinstance(prod_input, (int, str)) else prod_input.id
                det_remito = DetalleRemito.objects.select_for_update().filter(
                    remito=remito_obj, producto_id=prod_id
                ).first()
                if not det_remito:
                    raise ValidationError("El producto indicado no pertenece a este remito.")
            else:
                raise ValidationError("Cada ítem de devolución debe referenciar un renglón del remito.")

            cant_dev_raw = item_info.get('cantidad', 0)
            try:
                cant_dev = int(Decimal(str(cant_dev_raw)))
            except Exception:
                raise ValidationError(f"Cantidad de devolución inválida: '{cant_dev_raw}'.")

            if cant_dev <= 0:
                continue

            saldo_disponible = det_remito.cantidad - det_remito.cantidad_devuelta
            if cant_dev > saldo_disponible:
                raise ValidationError(
                    f"No se puede devolver {cant_dev} unidades del producto '{det_remito.descripcion_historica}'. "
                    f"El saldo disponible para devolución es {saldo_disponible} (remitido: {det_remito.cantidad})."
                )

            # Actualizar acumulado devuelto en el renglón del remito
            det_remito.cantidad_devuelta += cant_dev
            det_remito.save(update_fields=['cantidad_devuelta'])

            # Calcular total de la línea respetando el precio histórico y descuento del renglón
            subtotal_bruto = det_remito.precio_unitario_historico * Decimal(cant_dev)
            descuento = subtotal_bruto * (det_remito.porcentaje_descuento / Decimal('100.00'))
            total_linea = (subtotal_bruto - descuento).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

            DetalleNotaCredito.objects.create(
                nota_credito=nota_credito,
                detalle_remito=det_remito,
                cantidad=cant_dev,
                precio_unitario=det_remito.precio_unitario_historico,
                total_linea=total_linea
            )

            monto_total_nc += total_linea
            items_procesados += 1

            # Si reingresa a stock, restituir unidades base en Kardex
            if reingresa_stock_final:
                unidades_base_ingreso = cant_dev * det_remito.factor_unidades
                StockService.registrar_movimiento(
                    producto=det_remito.producto,
                    cantidad=unidades_base_ingreso,
                    tipo_movimiento='DEVOLUCION_NC',
                    documento_referencia=nota_credito.numero_nc,
                    usuario=operador,
                    motivo=f"Reingreso por {nota_credito.get_motivo_tipo_display()} N° {nota_credito.numero_nc}",
                    observaciones=observaciones or f"Devolución s/ Remito {remito_obj.numero_completo}"
                )

        if items_procesados == 0 or monto_total_nc <= Decimal('0.00'):
            raise ValidationError("La Nota de Crédito debe incluir al menos un ítem con cantidad mayor a cero.")

        nota_credito.monto_total = monto_total_nc
        nota_credito.save(update_fields=['monto_total'])

        return nota_credito

    @classmethod
    def registrar_devolucion_o_faltante(
        cls,
        remito,
        items_data,
        motivo_tipo='NC',
        reingresa_stock=False,
        usuario=None,
        observaciones=""
    ):
        return cls.registrar_nota_credito(
            remito=remito,
            items_data=items_data,
            motivo_tipo=motivo_tipo,
            reingresa_stock=reingresa_stock,
            usuario=usuario,
            observaciones=observaciones
        )

    @classmethod
    @transaction.atomic
    def emitir_remito_desde_pedido(cls, pedido, usuario_emisor=None, punto_venta=1):
        """
        Emite un Remito A4 a partir de un Pedido en estado APROBADO.
        """
        from pedidos.services import PedidoService
        return PedidoService.facturar_pedido_a_remito(
            pedido=pedido,
            supervisor=usuario_emisor,
            punto_venta=punto_venta
        )

    @classmethod
    @transaction.atomic
    def emitir_remito_directo(
        cls,
        cliente,
        vendedor=None,
        items_data=None,
        observaciones="",
        usuario_emisor=None,
        punto_venta=1,
        fecha=None,
        tipo_lista_precio=None,
        **kwargs
    ):
        """
        Emite un Remito A4 directo (venta mostrador / sin pedido previo).
        """
        return cls.emitir_remito(
            cliente=cliente,
            vendedor=vendedor or getattr(cliente, 'vendedor', None),
            supervisor=usuario_emisor,
            items=items_data,
            punto_venta=punto_venta,
            observaciones=observaciones,
            fecha=fecha,
            tipo_lista_precio=tipo_lista_precio,
            **kwargs
        )


# Alias de compatibilidad hacia atrás
ComprobanteService = RemitoService
