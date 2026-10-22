import json
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponseForbidden
from django.db.models import Q
from usuarios.models import Usuario
from clientes.models import Cliente, Vendedor
from productos.models import Producto, Categoria, PrecioProducto, Presentacion
from pedidos.models import Pedido, DetallePedido
from pedidos.services import PedidoService


# ==============================================================================
# AUTENTICACIÓN
# ==============================================================================

def login_view(request):
    next_url = request.POST.get('next') or request.GET.get('next', '')
    if request.user.is_authenticated:
        return _redirect_by_role(request.user, next_url, request)

    if request.method == 'POST':
        identificador = request.POST.get('identificador', '').strip()
        password = request.POST.get('password', '')

        if not identificador or not password:
            messages.error(request, 'Debe ingresar un identificador y contraseña.')
            return render(request, 'portal/login.html', {'next': next_url})

        user = authenticate(request, username=identificador, password=password)

        if user is not None:
            if not user.is_active:
                messages.error(request, 'La cuenta de usuario se encuentra inactiva.')
                return render(request, 'portal/login.html', {'next': next_url})

            login(request, user)
            messages.success(request, f'¡Bienvenido/a {user.nombre_completo}!')
            return _redirect_by_role(user, next_url, request)
        else:
            messages.error(request, 'Credenciales de acceso incorrectas.')

    return render(request, 'portal/login.html', {'next': next_url})


def logout_view(request):
    logout(request)
    messages.info(request, 'Has cerrado sesión correctamente.')
    return redirect('portal:login')


def _redirect_by_role(user, next_url=None, request=None):
    if next_url and request:
        from django.utils.http import url_has_allowed_host_and_scheme
        if url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
            # Aislamiento por rol: clientes y vendedores no pueden acceder a /gestion/
            if user.rol == 'CLIENTE' and not next_url.startswith('/gestion/'):
                return redirect(next_url)
            elif user.rol == 'VENDEDOR' and not next_url.startswith('/gestion/'):
                return redirect(next_url)
            elif user.rol in ['ADMIN', 'SUPERVISOR', 'FACTURACION', 'DEPOSITO'] or user.is_superuser:
                return redirect(next_url)

    # Destino habitual según rol
    if user.rol in ['ADMIN', 'SUPERVISOR', 'FACTURACION'] or user.is_superuser:
        return redirect('gestion:dashboard')
    elif user.rol == 'DEPOSITO':
        return redirect('gestion:deposito_pedidos')
    elif user.rol == 'VENDEDOR':
        return redirect('portal:vendedor_pedidos')
    elif user.rol == 'CLIENTE' or hasattr(user, 'perfil_cliente'):
        return redirect('portal:catalogo')
    return redirect('portal:catalogo')


# ==============================================================================
# PORTAL DE CLIENTES
# ==============================================================================

def _get_cliente_or_redirect(request):
    if not request.user.is_authenticated:
        return None
    if hasattr(request.user, 'perfil_cliente'):
        return request.user.perfil_cliente
    return None


@login_required
def catalogo_view(request):
    cliente = _get_cliente_or_redirect(request)
    if not cliente:
        if request.user.rol in ['VENDEDOR', 'ADMIN'] or request.user.is_superuser:
            return redirect('portal:vendedor_pedidos')
        messages.error(request, 'Su cuenta de usuario no tiene un perfil de cliente asignado.')
        return redirect('portal:login')

    query = request.GET.get('q', '').strip()
    categoria_id = request.GET.get('categoria', '').strip()

    productos_qs = Producto.objects.filter(activo=True).select_related('categoria', 'marca').prefetch_related('presentaciones')

    if query:
        productos_qs = productos_qs.filter(
            Q(codigo__icontains=query) |
            Q(nombre__icontains=query) |
            Q(descripcion__icontains=query) |
            Q(codigo_barras__icontains=query)
        )

    if categoria_id and categoria_id.isdigit():
        productos_qs = productos_qs.filter(categoria_id=int(categoria_id))

    lista_precio = cliente.tipo_lista_precio
    precios_map = {}
    if lista_precio:
        precios_qs = PrecioProducto.objects.filter(tipo_lista=lista_precio, producto__in=productos_qs)
        for p in precios_qs:
            precios_map[p.producto_id] = p

    productos_con_precio = []
    for prod in productos_qs:
        precio_obj = precios_map.get(prod.id)
        precio_final = precio_obj.precio_final if precio_obj else Decimal('0.00')
        precio_neto = precio_obj.precio_neto if precio_obj else Decimal('0.00')
        productos_con_precio.append({
            'producto': prod,
            'precio_obj': precio_obj,
            'precio_final': precio_final,
            'precio_neto': precio_neto,
            'presentaciones': prod.presentaciones.all()
        })

    # Borrador actual
    pedido = PedidoService.crear_o_recuperar_borrador(cliente)
    categorias = Categoria.objects.filter(activa=True)

    context = {
        'cliente': cliente,
        'productos_info': productos_con_precio,
        'categorias': categorias,
        'pedido': pedido,
        'query': query,
        'categoria_actual': int(categoria_id) if categoria_id.isdigit() else None
    }
    return render(request, 'portal/catalogo.html', context)


@login_required
def agregar_item_carrito_api(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)

    cliente = _get_cliente_or_redirect(request)
    if not cliente:
        return JsonResponse({'status': 'error', 'message': 'Usuario no es un cliente válido'}, status=403)

    try:
        if request.content_type == 'application/json':
            data = json.loads(request.body)
        else:
            data = request.POST

        producto_id = data.get('producto_id')
        presentacion_id = data.get('presentacion_id')
        cantidad_raw = data.get('cantidad', 1)

        try:
            cantidad = Decimal(str(cantidad_raw))
            if cantidad <= 0:
                raise ValueError()
        except Exception:
            return JsonResponse({'status': 'error', 'message': 'Cantidad inválida'}, status=400)

        producto = get_object_or_404(Producto, id=producto_id, activo=True)
        presentacion = Presentacion.objects.filter(id=presentacion_id, producto=producto).first() if presentacion_id else None

        pedido = PedidoService.crear_o_recuperar_borrador(cliente)
        item = PedidoService.agregar_item(pedido, producto, presentacion, cantidad)

        return JsonResponse({
            'status': 'ok',
            'message': f'Agregado {item.nombre_producto_historico} al carrito.',
            'cart_count': pedido.items.count(),
            'monto_subtotal_neto': str(pedido.monto_subtotal_neto),
            'monto_iva_total': str(pedido.monto_iva_total),
            'monto_total': str(pedido.monto_total),
            'monto_minimo': str(cliente.monto_minimo_pedido)
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@login_required
def carrito_view(request):
    cliente = _get_cliente_or_redirect(request)
    if not cliente:
        return redirect('portal:login')

    pedido = PedidoService.crear_o_recuperar_borrador(cliente)

    if request.method == 'POST':
        action = request.POST.get('action')
        item_id = request.POST.get('item_id')

        if action == 'update_quantity' and item_id:
            cantidad_raw = request.POST.get('cantidad', '1')
            try:
                cant = Decimal(str(cantidad_raw))
                item = DetallePedido.objects.get(id=item_id, pedido=pedido)
                if cant <= 0:
                    item.delete()
                else:
                    item.cantidad = cant
                    item.calcular_linea(save=True)
                pedido.recalcular_totales(save=True)
                messages.success(request, 'Cantidad actualizada correctamente.')
            except Exception as e:
                messages.error(request, f'Error al actualizar cantidad: {str(e)}')
            return redirect('portal:carrito')

    monto_minimo = cliente.monto_minimo_pedido or Decimal('0.00')
    monto_total = pedido.monto_total or Decimal('0.00')

    progreso_minimo = 100
    if monto_minimo > Decimal('0.00'):
        progreso = (monto_total / monto_minimo) * Decimal('100.00')
        progreso_minimo = min(100, int(progreso))

    cumple_minimo = (monto_total >= monto_minimo)

    context = {
        'cliente': cliente,
        'pedido': pedido,
        'monto_minimo': monto_minimo,
        'progreso_minimo': progreso_minimo,
        'cumple_minimo': cumple_minimo
    }
    return render(request, 'portal/carrito.html', context)


@login_required
def eliminar_item_carrito_view(request, item_id):
    cliente = _get_cliente_or_redirect(request)
    if not cliente:
        return redirect('portal:login')

    pedido = PedidoService.crear_o_recuperar_borrador(cliente)
    item = DetallePedido.objects.filter(id=item_id, pedido=pedido).first()
    if item:
        nombre = item.nombre_producto_historico
        item.delete()
        pedido.recalcular_totales(save=True)
        messages.success(request, f'Se eliminó "{nombre}" del pedido.')

    return redirect('portal:carrito')


@login_required
def enviar_pedido_view(request):
    if request.method != 'POST':
        return redirect('portal:carrito')

    cliente = _get_cliente_or_redirect(request)
    if not cliente:
        return redirect('portal:login')

    pedido = PedidoService.crear_o_recuperar_borrador(cliente)
    observaciones = request.POST.get('observaciones_cliente', '').strip()

    try:
        pedido_enviado = PedidoService.enviar_pedido(pedido, observaciones=observaciones)
        messages.success(request, f'¡Pedido {pedido_enviado.numero_pedido} enviado con éxito! Tu vendedor revisará la solicitud.')
        return redirect('portal:mis_pedidos')
    except Exception as e:
        messages.error(request, f'No se pudo enviar el pedido: {str(e)}')
        return redirect('portal:carrito')


@login_required
def mis_pedidos_view(request):
    cliente = _get_cliente_or_redirect(request)
    if not cliente:
        return redirect('portal:login')

    pedidos = Pedido.objects.filter(cliente=cliente).exclude(estado='BORRADOR').order_by('-fecha_creacion')

    context = {
        'cliente': cliente,
        'pedidos': pedidos
    }
    return render(request, 'portal/mis_pedidos.html', context)


@login_required
def detalle_pedido_view(request, pedido_id):
    cliente = _get_cliente_or_redirect(request)
    if not cliente:
        return redirect('portal:login')

    pedido = get_object_or_404(Pedido, id=pedido_id, cliente=cliente)

    context = {
        'cliente': cliente,
        'pedido': pedido
    }
    return render(request, 'portal/detalle_pedido.html', context)


# ==============================================================================
# PANEL MÓVIL DE VENDEDORES
# ==============================================================================

@login_required
def vendedor_pedidos_view(request):
    user = request.user
    if user.rol not in ['VENDEDOR', 'ADMIN', 'FACTURACION', 'DEPOSITO'] and not user.is_superuser:
        messages.error(request, 'No tienes permisos para acceder al panel de vendedor.')
        return redirect('portal:login')

    vendedor = getattr(user, 'perfil_vendedor', None)

    pedidos_qs = Pedido.objects.filter(
        estado__in=['PENDIENTE_REVISION', 'ENVIADO', 'EN_REVISION', 'APROBADO', 'RECHAZADO']
    ).select_related('cliente', 'vendedor')

    if vendedor and not user.is_superuser and user.rol == 'VENDEDOR':
        pedidos_qs = pedidos_qs.filter(vendedor=vendedor)

    estado_filter = request.GET.get('estado', 'PENDIENTE_REVISION')
    if estado_filter in ['ENVIADO', 'PENDIENTE_REVISION']:
        pedidos_qs = pedidos_qs.filter(estado__in=['PENDIENTE_REVISION', 'ENVIADO'])
    elif estado_filter:
        pedidos_qs = pedidos_qs.filter(estado=estado_filter)

    cliente_q = request.GET.get('q', '').strip()
    if cliente_q:
        pedidos_qs = pedidos_qs.filter(
            Q(cliente__razon_social__icontains=cliente_q) |
            Q(cliente__cuit__icontains=cliente_q) |
            Q(numero_pedido__icontains=cliente_q)
        )

    context = {
        'vendedor': vendedor,
        'pedidos': pedidos_qs.order_by('-fecha_envio', '-fecha_creacion'),
        'estado_filter': estado_filter,
        'query': cliente_q
    }
    return render(request, 'portal/vendedor/pedidos_revision.html', context)


@login_required
def vendedor_gestionar_pedido_view(request, pedido_id):
    user = request.user
    if user.rol not in ['VENDEDOR', 'ADMIN', 'FACTURACION'] and not user.is_superuser:
        return HttpResponseForbidden('Acceso no autorizado.')

    vendedor = getattr(user, 'perfil_vendedor', None)
    pedido = get_object_or_404(
        Pedido.objects.select_related('cliente', 'vendedor', 'lista_precio').prefetch_related('detalles'),
        id=pedido_id
    )

    if vendedor and not user.is_superuser and user.rol == 'VENDEDOR' and pedido.vendedor != vendedor:
        return HttpResponseForbidden('No tiene permisos para gestionar pedidos de otros vendedores.')

    if request.method == 'POST':
        accion = request.POST.get('accion')
        if accion == 'aprobar':
            try:
                PedidoService.aprobar_pedido(pedido, user)
                messages.success(request, f'Pedido {pedido.numero_pedido} aprobado exitosamente.')
            except Exception as e:
                messages.error(request, f'Error al aprobar pedido: {str(e)}')
            return redirect('portal:vendedor_pedidos')

        elif accion == 'rechazar':
            motivo = request.POST.get('motivo_rechazo', '').strip()
            try:
                PedidoService.rechazar_pedido(pedido, motivo, user)
                messages.warning(request, f'Pedido {pedido.numero_pedido} rechazado.')
            except Exception as e:
                messages.error(request, f'Error al rechazar pedido: {str(e)}')
            return redirect('portal:vendedor_pedidos')

    context = {
        'vendedor': vendedor,
        'pedido': pedido
    }
    return render(request, 'portal/vendedor/gestionar_pedido.html', context)


# ==============================================================================
# PRE-VENTA MÓVIL EN CALLE (VENDEDORES)
# ==============================================================================

@login_required
def vendedor_seleccionar_cliente_view(request):
    user = request.user
    if user.rol not in ['VENDEDOR', 'ADMIN'] and not user.is_superuser:
        messages.error(request, 'No tienes permisos para acceder a pre-venta en calle.')
        return redirect('portal:login')

    vendedor = getattr(user, 'perfil_vendedor', None)
    clientes_qs = Cliente.objects.filter(estado='ACTIVO').select_related('zona', 'localidad', 'vendedor', 'tipo_lista_precio')

    if vendedor and user.rol == 'VENDEDOR' and not user.is_superuser:
        clientes_qs = clientes_qs.filter(vendedor=vendedor)

    q = request.GET.get('q', '').strip()
    zona_id = request.GET.get('zona', '').strip()
    dia_id = request.GET.get('dia', '').strip()

    if q:
        clientes_qs = clientes_qs.filter(
            Q(razon_social__icontains=q) |
            Q(nombre_fantasia__icontains=q) |
            Q(cuit__icontains=q) |
            Q(domicilio__icontains=q)
        )

    if zona_id and zona_id.isdigit():
        clientes_qs = clientes_qs.filter(zona_id=int(zona_id))

    if dia_id and dia_id.isdigit():
        clientes_qs = clientes_qs.filter(dia_reparto=int(dia_id))

    from clientes.models import Zona
    context = {
        'vendedor': vendedor,
        'clientes': clientes_qs.order_by('razon_social'),
        'zonas': Zona.objects.all(),
        'dias_reparto': Cliente.DIAS_REPARTO,
        'query': q,
        'zona_actual': int(zona_id) if zona_id.isdigit() else None,
        'dia_actual': int(dia_id) if dia_id.isdigit() else None,
    }
    return render(request, 'portal/vendedor/seleccionar_cliente.html', context)


@login_required
def vendedor_tomar_pedido_view(request, cliente_id):
    user = request.user
    if user.rol not in ['VENDEDOR', 'ADMIN'] and not user.is_superuser:
        return HttpResponseForbidden('Acceso no autorizado.')

    vendedor = getattr(user, 'perfil_vendedor', None)
    cliente = get_object_or_404(Cliente, id=cliente_id, estado='ACTIVO')

    if vendedor and user.rol == 'VENDEDOR' and not user.is_superuser and cliente.vendedor != vendedor:
        return HttpResponseForbidden('No tiene permisos para tomar pedidos de clientes asignados a otros vendedores.')

    pedido = PedidoService.crear_o_recuperar_borrador_vendedor(cliente, user)

    query = request.GET.get('q', '').strip()
    categoria_id = request.GET.get('categoria', '').strip()

    productos_qs = Producto.objects.filter(activo=True).select_related('categoria', 'marca').prefetch_related('presentaciones')

    if query:
        productos_qs = productos_qs.filter(
            Q(codigo__icontains=query) |
            Q(nombre__icontains=query) |
            Q(descripcion__icontains=query) |
            Q(codigo_barras__icontains=query)
        )

    if categoria_id and categoria_id.isdigit():
        productos_qs = productos_qs.filter(categoria_id=int(categoria_id))

    lista_precio = cliente.tipo_lista_precio
    precios_map = {}
    if lista_precio:
        precios_qs = PrecioProducto.objects.filter(tipo_lista=lista_precio, producto__in=productos_qs)
        for p in precios_qs:
            precios_map[p.producto_id] = p

    productos_con_precio = []
    for prod in productos_qs:
        precio_obj = precios_map.get(prod.id)
        precio_final = precio_obj.precio_final if precio_obj else Decimal('0.00')
        precio_neto = precio_obj.precio_neto if precio_obj else Decimal('0.00')
        productos_con_precio.append({
            'producto': prod,
            'precio_obj': precio_obj,
            'precio_final': precio_final,
            'precio_neto': precio_neto,
            'presentaciones': prod.presentaciones.all()
        })

    categorias = Categoria.objects.filter(activa=True)

    context = {
        'vendedor': vendedor,
        'cliente': cliente,
        'pedido': pedido,
        'productos_info': productos_con_precio,
        'categorias': categorias,
        'query': query,
        'categoria_actual': int(categoria_id) if categoria_id.isdigit() else None
    }
    return render(request, 'portal/vendedor/tomar_pedido.html', context)


@login_required
def vendedor_agregar_item_api(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)

    user = request.user
    if user.rol not in ['VENDEDOR', 'ADMIN'] and not user.is_superuser:
        return JsonResponse({'status': 'error', 'message': 'Acceso no autorizado'}, status=403)

    try:
        if request.content_type == 'application/json':
            data = json.loads(request.body)
        else:
            data = request.POST

        cliente_id = data.get('cliente_id')
        producto_id = data.get('producto_id')
        presentacion_id = data.get('presentacion_id')
        cantidad_raw = data.get('cantidad', 1)
        descuento_extra_raw = data.get('descuento_extra', 0)

        vendedor = getattr(user, 'perfil_vendedor', None)
        cliente = get_object_or_404(Cliente, id=cliente_id, estado='ACTIVO')

        if vendedor and user.rol == 'VENDEDOR' and not user.is_superuser and cliente.vendedor != vendedor:
            return JsonResponse({'status': 'error', 'message': 'Cliente no pertenece a su cartera'}, status=403)

        try:
            cantidad = Decimal(str(cantidad_raw))
            if cantidad <= 0:
                raise ValueError()
        except Exception:
            return JsonResponse({'status': 'error', 'message': 'Cantidad inválida'}, status=400)

        try:
            descuento_extra = Decimal(str(descuento_extra_raw or 0))
        except Exception:
            descuento_extra = Decimal('0.00')

        producto = get_object_or_404(Producto, id=producto_id, activo=True)
        presentacion = Presentacion.objects.filter(id=presentacion_id, producto=producto).first() if presentacion_id else None

        pedido = PedidoService.crear_o_recuperar_borrador_vendedor(cliente, user)
        item = PedidoService.agregar_item(pedido, producto, presentacion, cantidad, descuento_extra=descuento_extra)

        return JsonResponse({
            'status': 'ok',
            'message': f'Agregado {item.nombre_producto_historico} al borrador.',
            'cart_count': pedido.items.count(),
            'monto_subtotal_neto': str(pedido.monto_subtotal_neto),
            'monto_iva_total': str(pedido.monto_iva_total),
            'monto_total': str(pedido.monto_total)
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@login_required
def vendedor_confirmar_pedido_view(request, pedido_id):
    if request.method != 'POST':
        return redirect('portal:vendedor_pedidos')

    user = request.user
    if user.rol not in ['VENDEDOR', 'ADMIN'] and not user.is_superuser:
        return HttpResponseForbidden('Acceso no autorizado.')

    vendedor = getattr(user, 'perfil_vendedor', None)
    pedido = get_object_or_404(Pedido, id=pedido_id, estado='BORRADOR')

    if vendedor and user.rol == 'VENDEDOR' and not user.is_superuser and pedido.cliente.vendedor != vendedor:
        return HttpResponseForbidden('No tiene permisos sobre este pedido.')

    try:
        pedido_confirmado = PedidoService.confirmar_pedido_preventa(pedido, user)
        messages.success(request, f'¡Pedido {pedido_confirmado.numero_pedido} registrado y aprobado exitosamente para {pedido_confirmado.cliente.razon_social}!')
        return redirect('portal:vendedor_pedidos')
    except Exception as e:
        messages.error(request, f'Error al confirmar pedido de pre-venta: {str(e)}')
        return redirect('portal:vendedor_tomar_pedido', cliente_id=pedido.cliente.id)

