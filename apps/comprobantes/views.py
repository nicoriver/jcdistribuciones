from decimal import Decimal
from datetime import datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views import View
from django.contrib import messages
from django.http import HttpResponseForbidden
from django.db.models import Q
from clientes.models import Cliente, Vendedor
from productos.models import Producto, Presentacion
from pedidos.models import Pedido
from .models import Remito, DetalleRemito, NotaCreditoInterna, DetalleNotaCredito
from .services import RemitoService, ComprobanteService


def _check_permisos_comprobantes(user):
    return (
        getattr(user, 'rol', None) in ['ADMIN', 'SUPERVISOR', 'FACTURACION', 'DEPOSITO']
        or user.is_staff
        or user.is_superuser
    )


@method_decorator(login_required, name='dispatch')
class RemitoImpresionView(View):
    """
    Vista web para renderizar el Remito Comercial en formato A4 listo para imprimir
    o guardar como PDF mediante window.print().
    No discrimina visualmente el IVA; expone cantidades, presentaciones, descuentos por renglón y total final.
    """
    template_name = 'comprobantes/remito_a4.html'

    def get(self, request, remito_id=None, pk=None):
        target_id = remito_id or pk
        remito = get_object_or_404(
            Remito.objects.select_related(
                'cliente',
                'cliente__localidad',
                'cliente__localidad__provincia',
                'cliente__zona',
                'vendedor',
                'supervisor',
                'pedido'
            ).prefetch_related('detalles', 'detalles__presentacion'),
            id=target_id
        )

        detalles = list(remito.detalles.all())
        from .services import calcular_paginacion_remito_a4
        paginas = calcular_paginacion_remito_a4(detalles, has_observaciones=bool(remito.observaciones))
        context = {
            'remito': remito,
            'cliente': remito.cliente,
            'detalles': detalles,
            'items': detalles,
            'paginas': paginas,
        }
        return render(request, self.template_name, context)


imprimir_remito_view = RemitoImpresionView.as_view()


@login_required
def emitir_remito_view(request, pedido_id):
    """
    Vista de emisión de Remito A4 para supervisores y operadores autorizados.
    """
    user = request.user
    if not _check_permisos_comprobantes(user):
        return HttpResponseForbidden('Acceso no autorizado.')

    pedido = get_object_or_404(Pedido, id=pedido_id)

    try:
        remito = RemitoService.emitir_remito_desde_pedido(pedido, user)
        messages.success(request, f"Remito {remito.numero_completo} generado correctamente.")
        return redirect('comprobantes:imprimir_remito', remito_id=remito.id)
    except Exception as e:
        messages.error(request, f"Error al emitir remito: {str(e)}")
        return redirect('portal:vendedor_gestionar_pedido', pedido_id=pedido.id)


@login_required
def remitos_list_view(request):
    """
    Bandeja de control de Remitos emitidos con acciones directas (Imprimir A4, Faltante NCF, Devolución NC).
    """
    if not _check_permisos_comprobantes(request.user):
        return HttpResponseForbidden('Acceso no autorizado.')

    remitos_qs = Remito.objects.select_related('cliente', 'vendedor', 'supervisor', 'pedido').prefetch_related('notas_credito', 'detalles')

    q = request.GET.get('q', '').strip()
    estado = request.GET.get('estado', '').strip()
    desde_str = request.GET.get('desde', '').strip()
    hasta_str = request.GET.get('hasta', '').strip()

    if q:
        remitos_qs = remitos_qs.filter(
            Q(numero_completo__icontains=q) |
            Q(cliente__razon_social__icontains=q) |
            Q(cliente__cuit__icontains=q) |
            Q(pedido__numero_pedido__icontains=q)
        )

    if estado:
        remitos_qs = remitos_qs.filter(estado=estado)

    if desde_str:
        try:
            desde_obj = datetime.strptime(desde_str, '%Y-%m-%d').date()
            remitos_qs = remitos_qs.filter(fecha_emision__date__gte=desde_obj)
        except ValueError:
            pass

    if hasta_str:
        try:
            hasta_obj = datetime.strptime(hasta_str, '%Y-%m-%d').date()
            remitos_qs = remitos_qs.filter(fecha_emision__date__lte=hasta_obj)
        except ValueError:
            pass

    context = {
        'remitos': remitos_qs.order_by('-fecha_emision'),
        'query': q,
        'estado_actual': estado,
        'desde': desde_str,
        'hasta': hasta_str
    }
    return render(request, 'comprobantes/remitos_list.html', context)


@login_required
def registrar_faltante_ncf_view(request, remito_id):
    """
    Formulario web para registrar Faltante de Carga/Despacho (NCF) sin reingreso de stock.
    """
    if not _check_permisos_comprobantes(request.user):
        return HttpResponseForbidden('Acceso no autorizado.')

    remito = get_object_or_404(
        Remito.objects.select_related('cliente', 'vendedor').prefetch_related('detalles'),
        id=remito_id
    )

    if request.method == 'POST':
        observaciones = request.POST.get('observaciones', '').strip()
        items_data = []

        for item in remito.detalles.all():
            cant_raw = request.POST.get(f'cant_faltante_{item.id}', '0').strip()
            try:
                cant = int(Decimal(cant_raw))
                if cant > 0:
                    items_data.append({
                        'detalle_remito_id': item.id,
                        'cantidad': cant
                    })
            except Exception:
                pass

        if not items_data:
            messages.error(request, 'Debe indicar una cantidad mayor a cero en al menos un renglón.')
            return render(request, 'comprobantes/form_faltante_ncf.html', {'remito': remito})

        try:
            nc = RemitoService.registrar_nota_credito(
                remito=remito,
                items_data=items_data,
                motivo_tipo='NCF',
                reingresa_stock=False,
                usuario=request.user,
                observaciones=observaciones
            )
            messages.success(request, f"Nota de Crédito por Faltante {nc.numero_nc} generada correctamente.")
            return redirect('comprobantes:imprimir_nota_credito', nc_id=nc.id)
        except Exception as e:
            messages.error(request, f"Error al registrar faltante: {str(e)}")
            return render(request, 'comprobantes/form_faltante_ncf.html', {'remito': remito})

    return render(request, 'comprobantes/form_faltante_ncf.html', {'remito': remito})


@login_required
def registrar_devolucion_nc_view(request, remito_id):
    """
    Formulario web para registrar Devolución de Mercadería (NC) con opción de reingreso a stock.
    """
    if not _check_permisos_comprobantes(request.user):
        return HttpResponseForbidden('Acceso no autorizado.')

    remito = get_object_or_404(
        Remito.objects.select_related('cliente', 'vendedor').prefetch_related('detalles'),
        id=remito_id
    )

    if request.method == 'POST':
        observaciones = request.POST.get('observaciones', '').strip()
        reingresa_stock = request.POST.get('reingresa_stock') in ['on', 'true', 'True', '1']
        items_data = []

        for item in remito.detalles.all():
            cant_raw = request.POST.get(f'cant_dev_{item.id}', '0').strip()
            try:
                cant = int(Decimal(cant_raw))
                if cant > 0:
                    items_data.append({
                        'detalle_remito_id': item.id,
                        'cantidad': cant
                    })
            except Exception:
                pass

        if not items_data:
            messages.error(request, 'Debe indicar una cantidad mayor a cero en al menos un renglón.')
            return render(request, 'comprobantes/form_devolucion_nc.html', {'remito': remito})

        try:
            nc = RemitoService.registrar_nota_credito(
                remito=remito,
                items_data=items_data,
                motivo_tipo='NC',
                reingresa_stock=reingresa_stock,
                usuario=request.user,
                observaciones=observaciones
            )
            messages.success(request, f"Nota de Crédito por Devolución {nc.numero_nc} generada correctamente.")
            return redirect('comprobantes:imprimir_nota_credito', nc_id=nc.id)
        except Exception as e:
            messages.error(request, f"Error al registrar devolución: {str(e)}")
            return render(request, 'comprobantes/form_devolucion_nc.html', {'remito': remito})

    return render(request, 'comprobantes/form_devolucion_nc.html', {'remito': remito})


@login_required
def imprimir_nota_credito_view(request, nc_id):
    """
    Vista responsiva e imprimible en formato A4 para Nota de Crédito Interna (NCF o NC).
    """
    nc = get_object_or_404(
        NotaCreditoInterna.objects.select_related(
            'remito', 'remito__cliente', 'remito__cliente__localidad',
            'remito__cliente__localidad__provincia', 'remito__cliente__zona',
            'remito__vendedor', 'usuario'
        ).prefetch_related('items', 'items__detalle_remito'),
        id=nc_id
    )

    context = {
        'nc': nc,
        'remito': nc.remito,
        'cliente': nc.remito.cliente,
        'items': nc.items.all()
    }
    return render(request, 'comprobantes/nota_credito_a4.html', context)


@login_required
def remito_crear_directo_view(request):
    """
    Vista de creación directa de Remito (Venta mostrador / sin pedido previo).
    """
    if not _check_permisos_comprobantes(request.user):
        return HttpResponseForbidden('Acceso no autorizado.')

    if request.method == 'POST':
        cliente_id = request.POST.get('cliente_id')
        vendedor_id = request.POST.get('vendedor_id')
        observaciones = request.POST.get('observaciones', '').strip()

        cliente = get_object_or_404(Cliente, id=cliente_id) if cliente_id else None
        vendedor = Vendedor.objects.filter(id=vendedor_id).first() if vendedor_id else (cliente.vendedor if cliente else None)

        prod_ids = request.POST.getlist('producto_id[]') or request.POST.getlist('producto_id')
        pres_ids = request.POST.getlist('presentacion_id[]') or request.POST.getlist('presentacion_id')
        cantidades = request.POST.getlist('cantidad[]') or request.POST.getlist('cantidad')
        precios = request.POST.getlist('precio_unitario[]') or request.POST.getlist('precio_unitario')
        descuentos = request.POST.getlist('descuento_porcentaje[]') or request.POST.getlist('descuento_porcentaje')

        items_data = []
        for idx in range(len(prod_ids)):
            p_id = prod_ids[idx]
            if not p_id:
                continue
            producto = Producto.objects.filter(id=p_id).first()
            if not producto:
                continue

            pres_id = pres_ids[idx] if idx < len(pres_ids) else None
            presentacion = Presentacion.objects.filter(id=pres_id, producto=producto).first() if pres_id else None

            cant_val = cantidades[idx] if idx < len(cantidades) else '0'
            precio_val = precios[idx] if idx < len(precios) else '0'
            desc_val = descuentos[idx] if idx < len(descuentos) else '0'

            try:
                cant_int = int(Decimal(cant_val))
                if cant_int > 0:
                    items_data.append({
                        'producto': producto,
                        'presentacion': presentacion,
                        'cantidad': cant_int,
                        'precio_unitario': Decimal(precio_val),
                        'porcentaje_descuento': Decimal(desc_val or '0.00')
                    })
            except Exception:
                pass

        try:
            remito = RemitoService.emitir_remito_directo(
                cliente=cliente,
                vendedor=vendedor,
                items_data=items_data,
                observaciones=observaciones,
                usuario_emisor=request.user
            )
            messages.success(request, f"Remito Directo {remito.numero_completo} emitido exitosamente.")
            return redirect('comprobantes:imprimir_remito', remito_id=remito.id)
        except Exception as e:
            messages.error(request, f"Error al emitir el remito: {str(e)}")
            return redirect('comprobantes:remito_crear_directo')

    clientes = Cliente.objects.filter(estado='ACTIVO').select_related('vendedor', 'tipo_lista_precio').order_by('razon_social')
    vendedores = Vendedor.objects.filter(activo=True).order_by('apellido', 'nombre')
    productos = Producto.objects.filter(activo=True).select_related('categoria', 'marca').prefetch_related('presentaciones', 'precios', 'precios__tipo_lista').order_by('nombre')

    context = {
        'clientes': clientes,
        'vendedores': vendedores,
        'productos': productos,
    }
    return render(request, 'comprobantes/form_remito_directo.html', context)
