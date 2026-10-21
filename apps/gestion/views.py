from decimal import Decimal
from datetime import datetime
from functools import wraps
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views import View
from django.contrib import messages
from django.http import HttpResponseForbidden, HttpResponseBadRequest
from django.db import models
from django.db.models import Q, F, Sum
from django.utils import timezone

from clientes.models import Cliente, Vendedor
from geografia.models import Zona
from productos.models import Producto, Presentacion, Categoria, Marca, TipoListaPrecio, ListaPrecio, PrecioProducto
from pedidos.models import Pedido
from pedidos.services import PedidoService
from compras.models import Compra
from comprobantes.models import Remito
from comprobantes.services import RemitoService
from .forms import ClienteForm, ProductoForm, PrecioProductoForm, ListaPrecioForm


def role_required(allowed_roles):
    """
    Decorador RBAC para restringir vistas a roles específicos (ej: ['SUPERVISOR', 'ADMIN']).
    Si el usuario está autenticado pero su rol no está autorizado (ej. CLIENTE o VENDEDOR),
    retorna HTTP 403 Forbidden.
    """
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped_view(request, *args, **kwargs):
            user = request.user
            user_rol = getattr(user, 'rol', None)
            if user.is_superuser or user_rol in allowed_roles:
                return view_func(request, *args, **kwargs)
            return HttpResponseForbidden('Acceso denegado: no posee los permisos de rol requeridos (403 Forbidden).')
        return _wrapped_view
    return decorator


def _check_permisos_gestion(user):
    return getattr(user, 'rol', None) in ['SUPERVISOR', 'ADMIN', 'FACTURACION'] or user.is_superuser


def _check_permisos_deposito(user):
    return getattr(user, 'rol', None) in ['SUPERVISOR', 'ADMIN', 'DEPOSITO', 'FACTURACION'] or user.is_superuser


@method_decorator(role_required(['SUPERVISOR', 'ADMIN', 'FACTURACION']), name='dispatch')
class DashboardSupervisorView(View):
    """
    Mesa de Control Principal del Supervisor (/gestion/):
    Muestra métricas operativas clave:
    - Pedidos aprobados pendientes de facturar
    - Remitos emitidos hoy
    - Compras registradas en el mes
    - Productos con stock bajo punto de reposición
    """
    template_name = 'gestion/dashboard.html'

    def get(self, request):
        ahora = timezone.now()
        hoy = ahora.date()

        # 1. Pedidos para facturar (en estado APROBADO)
        pedidos_para_facturar = Pedido.objects.filter(estado='APROBADO').count()
        pedidos_en_revision = Pedido.objects.filter(estado__in=['PENDIENTE_REVISION', 'ENVIADO', 'EN_REVISION']).count()

        # 2. Remitos emitidos hoy
        remitos_hoy_qs = Remito.objects.filter(fecha_emision__date=hoy, anulado=False)
        remitos_emitidos_hoy = remitos_hoy_qs.count()
        remitos_hoy_monto = remitos_hoy_qs.aggregate(total=Sum('monto_total'))['total'] or Decimal('0.00')

        # 3. Compras del mes
        compras_mes_qs = Compra.objects.filter(
            fecha_emision__year=hoy.year,
            fecha_emision__month=hoy.month
        )
        compras_mes_count = compras_mes_qs.count()
        compras_mes_monto = compras_mes_qs.aggregate(total=Sum('total_compra'))['total'] or Decimal('0.00')

        # 4. Productos con stock bajo punto de reposición
        productos_stock_bajo_qs = Producto.objects.filter(
            activo=True,
            controla_stock=True,
            stock_actual__lte=F('punto_reposicion')
        ).select_related('categoria', 'marca', 'proveedor_habitual').order_by('stock_actual')
        productos_stock_critico = productos_stock_bajo_qs.count()

        # Pedidos creados hoy
        pedidos_hoy_qs = Pedido.objects.filter(fecha_creacion__date=hoy)
        pedidos_hoy_count = pedidos_hoy_qs.count()
        pedidos_hoy_monto = pedidos_hoy_qs.aggregate(total=Sum('total_estimado'))['total'] or Decimal('0.00')

        ultimos_pedidos = Pedido.objects.select_related('cliente', 'vendedor').order_by('-fecha_creacion')[:6]
        ultimos_remitos = Remito.objects.select_related('cliente', 'vendedor', 'supervisor').order_by('-fecha_emision')[:6]

        context = {
            'pedidos_para_facturar': pedidos_para_facturar,
            'pedidos_pendientes_despacho': pedidos_para_facturar,
            'pedidos_en_revision': pedidos_en_revision,
            'remitos_emitidos_hoy': remitos_emitidos_hoy,
            'remitos_hoy_monto': remitos_hoy_monto,
            'compras_mes_count': compras_mes_count,
            'compras_mes_monto': compras_mes_monto,
            'productos_stock_critico': productos_stock_critico,
            'productos_stock_bajo': productos_stock_bajo_qs[:10],
            'pedidos_hoy_count': pedidos_hoy_count,
            'pedidos_hoy_monto': pedidos_hoy_monto,
            'ultimos_pedidos': ultimos_pedidos,
            'ultimos_remitos': ultimos_remitos,
        }
        return render(request, self.template_name, context)


dashboard_view = DashboardSupervisorView.as_view()


@method_decorator(role_required(['SUPERVISOR', 'ADMIN', 'FACTURACION']), name='dispatch')
class BandejaFacturacionView(View):
    """
    Bandeja de Facturación del Supervisor (/gestion/facturacion/):
    Lista los pedidos en estado APROBADO con filtros por zona y vendedor,
    permitiendo facturarlos en un clic generando el Remito A4.
    """
    template_name = 'gestion/bandeja_facturacion.html'

    def get(self, request):
        pedidos_qs = (
            Pedido.objects.filter(estado='APROBADO')
            .select_related('cliente', 'cliente__zona', 'vendedor', 'lista_precio')
            .prefetch_related('detalles', 'detalles__producto', 'detalles__presentacion')
        )

        zona_id = request.GET.get('zona', '').strip()
        vendedor_id = request.GET.get('vendedor', '').strip()
        q = request.GET.get('q', '').strip()

        if zona_id and zona_id.isdigit():
            pedidos_qs = pedidos_qs.filter(cliente__zona_id=int(zona_id))

        if vendedor_id and vendedor_id.isdigit():
            pedidos_qs = pedidos_qs.filter(vendedor_id=int(vendedor_id))

        if q:
            pedidos_qs = pedidos_qs.filter(
                Q(numero_pedido__icontains=q) |
                Q(cliente__razon_social__icontains=q) |
                Q(cliente__cuit__icontains=q)
            )

        context = {
            'pedidos_aprobados': pedidos_qs.order_by('fecha_creacion'),
            'zonas': Zona.objects.filter(activa=True).order_by('nombre'),
            'vendedores': Vendedor.objects.filter(activo=True).order_by('apellido', 'nombre'),
            'zona_actual': int(zona_id) if zona_id.isdigit() else None,
            'vendedor_actual': int(vendedor_id) if vendedor_id.isdigit() else None,
            'query': q,
        }
        return render(request, self.template_name, context)


bandeja_facturacion_view = BandejaFacturacionView.as_view()


@method_decorator(role_required(['SUPERVISOR', 'ADMIN', 'FACTURACION']), name='dispatch')
class FacturarPedidoActionView(View):
    """
    Endpoint POST que ejecuta PedidoService.facturar_pedido_a_remito(pedido, supervisor)
    y redirige inmediatamente a la vista de impresión del Remito A4 (/comprobantes/remito/<id>/imprimir/).
    """

    def post(self, request, pedido_id):
        pedido = get_object_or_404(Pedido, id=pedido_id)
        try:
            remito = PedidoService.facturar_pedido_a_remito(pedido=pedido, supervisor=request.user)
            messages.success(
                request,
                f"Pedido {pedido.numero_pedido} facturado exitosamente. Remito generado: {remito.numero_completo}."
            )
            return redirect('comprobantes:imprimir_remito', remito_id=remito.id)
        except Exception as e:
            messages.error(request, f"No se pudo facturar el pedido: {str(e)}")
            return HttpResponseBadRequest(f"Error al facturar el pedido: {str(e)}")


facturar_pedido_action_view = FacturarPedidoActionView.as_view()


@method_decorator(role_required(['SUPERVISOR', 'ADMIN', 'FACTURACION']), name='dispatch')
class VentaDirectaRemitoView(View):
    """
    Formulario interactivo (/gestion/remito-directo/) para emitir un Remito A4
    sin pedido previo (venta directa de mostrador / despacho inmediato).
    """
    template_name = 'gestion/remito_directo.html'

    def get(self, request):
        clientes = Cliente.objects.filter(activo=True).select_related('vendedor', 'zona', 'tipo_lista_precio').order_by('razon_social')
        vendedores = Vendedor.objects.filter(activo=True).order_by('apellido', 'nombre')
        productos = (
            Producto.objects.filter(activo=True)
            .select_related('categoria', 'marca')
            .prefetch_related('presentaciones', 'precios', 'precios__tipo_lista')
            .order_by('nombre')
        )
        context = {
            'clientes': clientes,
            'vendedores': vendedores,
            'productos': productos,
        }
        return render(request, self.template_name, context)

    def post(self, request):
        cliente_id = request.POST.get('cliente_id')
        vendedor_id = request.POST.get('vendedor_id')
        observaciones = request.POST.get('observaciones', '').strip()

        cliente = get_object_or_404(Cliente, id=cliente_id) if cliente_id else None
        vendedor = (
            Vendedor.objects.filter(id=vendedor_id).first()
            if vendedor_id
            else (cliente.vendedor if cliente else None)
        )

        prod_ids = request.POST.getlist('producto_id[]') or request.POST.getlist('producto_id')
        pres_ids = request.POST.getlist('presentacion_id[]') or request.POST.getlist('presentacion_id')
        cantidades = request.POST.getlist('cantidad[]') or request.POST.getlist('cantidad')
        precios = request.POST.getlist('precio_unitario[]') or request.POST.getlist('precio_unitario')
        descuentos = request.POST.getlist('porcentaje_descuento[]') or request.POST.getlist('descuento_porcentaje[]') or request.POST.getlist('porcentaje_descuento')

        items_data = []
        for idx in range(len(prod_ids)):
            p_id = prod_ids[idx]
            if not p_id:
                continue
            producto = Producto.objects.filter(id=p_id).first()
            if not producto:
                continue

            pres_id = pres_ids[idx] if idx < len(pres_ids) and pres_ids[idx] else None
            presentacion = Presentacion.objects.filter(id=pres_id, producto=producto).first() if pres_id else None

            cant_val = cantidades[idx] if idx < len(cantidades) else '0'
            precio_val = precios[idx] if idx < len(precios) and precios[idx] != '' else None
            desc_val = descuentos[idx] if idx < len(descuentos) and descuentos[idx] != '' else '0.00'

            try:
                cant_int = int(Decimal(str(cant_val)))
                if cant_int > 0:
                    item_dict = {
                        'producto': producto,
                        'presentacion': presentacion,
                        'factor_unidades': int(presentacion.factor_conversion) if presentacion else 1,
                        'cantidad': cant_int,
                        'porcentaje_descuento': Decimal(str(desc_val)),
                    }
                    if precio_val is not None:
                        item_dict['precio_unitario_historico'] = Decimal(str(precio_val))
                    items_data.append(item_dict)
            except Exception:
                pass

        try:
            remito = RemitoService.emitir_remito(
                cliente=cliente,
                vendedor=vendedor,
                supervisor=request.user,
                items=items_data,
                observaciones=observaciones
            )
            messages.success(request, f"Remito directo {remito.numero_completo} emitido correctamente.")
            return redirect('comprobantes:imprimir_remito', remito_id=remito.id)
        except Exception as e:
            messages.error(request, f"Error al emitir remito directo: {str(e)}")
            return redirect('gestion:remito_directo')


remito_directo_view = VentaDirectaRemitoView.as_view()


# ==============================================================================
# MÓDULO DE CLIENTES
# ==============================================================================

@role_required(['SUPERVISOR', 'ADMIN', 'FACTURACION'])
def clientes_list_view(request):
    clientes_qs = Cliente.objects.select_related('zona', 'localidad', 'vendedor', 'tipo_lista_precio', 'condicion_iva')

    q = request.GET.get('q', '').strip()
    vendedor_id = request.GET.get('vendedor', '').strip()
    zona_id = request.GET.get('zona', '').strip()
    estado = request.GET.get('estado', '').strip()

    if q:
        clientes_qs = clientes_qs.filter(
            Q(razon_social__icontains=q) |
            Q(nombre_fantasia__icontains=q) |
            Q(cuit__icontains=q) |
            Q(domicilio__icontains=q)
        )

    if vendedor_id and vendedor_id.isdigit():
        clientes_qs = clientes_qs.filter(vendedor_id=int(vendedor_id))

    if zona_id and zona_id.isdigit():
        clientes_qs = clientes_qs.filter(zona_id=int(zona_id))

    if estado:
        clientes_qs = clientes_qs.filter(estado=estado)

    context = {
        'clientes': clientes_qs.order_by('razon_social'),
        'vendedores': Vendedor.objects.filter(activo=True),
        'zonas': Zona.objects.all(),
        'query': q,
        'vendedor_actual': int(vendedor_id) if vendedor_id.isdigit() else None,
        'zona_actual': int(zona_id) if zona_id.isdigit() else None,
        'estado_actual': estado,
    }
    return render(request, 'gestion/clientes_list.html', context)


@role_required(['SUPERVISOR', 'ADMIN', 'FACTURACION'])
def cliente_crear_view(request):
    if request.method == 'POST':
        form = ClienteForm(request.POST)
        if form.is_valid():
            cliente = form.save()
            messages.success(request, f"Cliente '{cliente.razon_social}' registrado exitosamente.")
            return redirect('gestion:clientes_list')
    else:
        form = ClienteForm()

    context = {
        'form': form,
        'titulo': 'Registrar Nuevo Cliente'
    }
    return render(request, 'gestion/cliente_form.html', context)


@role_required(['SUPERVISOR', 'ADMIN', 'FACTURACION'])
def cliente_editar_view(request, cliente_id):
    cliente = get_object_or_404(Cliente, id=cliente_id)

    if request.method == 'POST':
        form = ClienteForm(request.POST, instance=cliente)
        if form.is_valid():
            cliente = form.save()
            messages.success(request, f"Cliente '{cliente.razon_social}' actualizado correctamente.")
            return redirect('gestion:clientes_list')
    else:
        form = ClienteForm(instance=cliente)

    context = {
        'form': form,
        'cliente': cliente,
        'titulo': f'Editar Cliente: {cliente.razon_social}'
    }
    return render(request, 'gestion/cliente_form.html', context)


# ==============================================================================
# MÓDULO DE PRODUCTOS Y PRECIOS
# ==============================================================================

@role_required(['SUPERVISOR', 'ADMIN', 'FACTURACION'])
def productos_list_view(request):
    productos_qs = Producto.objects.select_related('categoria', 'marca').prefetch_related('precios', 'precios__tipo_lista')

    q = request.GET.get('q', '').strip()
    categoria_id = request.GET.get('categoria', '').strip()
    marca_id = request.GET.get('marca', '').strip()
    stock_bajo = request.GET.get('stock_bajo', '').strip()

    if q:
        productos_qs = productos_qs.filter(
            Q(codigo__icontains=q) |
            Q(codigo_barras__icontains=q) |
            Q(nombre__icontains=q)
        )

    if categoria_id and categoria_id.isdigit():
        productos_qs = productos_qs.filter(categoria_id=int(categoria_id))

    if marca_id and marca_id.isdigit():
        productos_qs = productos_qs.filter(marca_id=int(marca_id))

    if stock_bajo == '1':
        productos_qs = productos_qs.filter(controla_stock=True, stock_actual__lte=F('punto_reposicion'))

    context = {
        'productos': productos_qs.order_by('nombre'),
        'categorias': Categoria.objects.filter(activa=True),
        'marcas': Marca.objects.filter(activa=True),
        'listas_precio': TipoListaPrecio.objects.filter(activa=True),
        'query': q,
        'categoria_actual': int(categoria_id) if categoria_id.isdigit() else None,
        'marca_actual': int(marca_id) if marca_id.isdigit() else None,
        'stock_bajo': stock_bajo,
    }
    return render(request, 'gestion/productos_list.html', context)


@role_required(['SUPERVISOR', 'ADMIN', 'FACTURACION'])
def producto_crear_view(request):
    listas_activas = TipoListaPrecio.objects.filter(activa=True)

    if request.method == 'POST':
        form = ProductoForm(request.POST)
        if form.is_valid():
            producto = form.save()
            for lista in listas_activas:
                recargo_raw = request.POST.get(f'recargo_lista_{lista.id}', '0').strip()
                descuento_raw = request.POST.get(f'descuento_lista_{lista.id}', '0').strip()
                try:
                    recargo = Decimal(recargo_raw)
                except Exception:
                    recargo = Decimal('0.00')
                try:
                    descuento = Decimal(descuento_raw)
                except Exception:
                    descuento = Decimal('0.00')

                precio_obj, _ = PrecioProducto.objects.get_or_create(tipo_lista=lista, producto=producto)
                precio_obj.porcentaje_recargo = recargo
                precio_obj.porcentaje_descuento = descuento
                precio_obj.calcular_y_guardar(save=True)

            messages.success(request, f"Producto '{producto.nombre}' registrado con sus listas de precios.")
            return redirect('gestion:productos_list')
    else:
        form = ProductoForm()

    context = {
        'form': form,
        'listas_activas': listas_activas,
        'titulo': 'Registrar Nuevo Producto'
    }
    return render(request, 'gestion/producto_form.html', context)


@role_required(['SUPERVISOR', 'ADMIN', 'FACTURACION'])
def producto_editar_view(request, producto_id):
    producto = get_object_or_404(Producto, id=producto_id)
    listas_activas = TipoListaPrecio.objects.filter(activa=True)

    if request.method == 'POST':
        form = ProductoForm(request.POST, instance=producto)
        if form.is_valid():
            producto = form.save()
            for lista in listas_activas:
                recargo_raw = request.POST.get(f'recargo_lista_{lista.id}', '0').strip()
                descuento_raw = request.POST.get(f'descuento_lista_{lista.id}', '0').strip()
                try:
                    recargo = Decimal(recargo_raw)
                except Exception:
                    recargo = Decimal('0.00')
                try:
                    descuento = Decimal(descuento_raw)
                except Exception:
                    descuento = Decimal('0.00')

                precio_obj, _ = PrecioProducto.objects.get_or_create(tipo_lista=lista, producto=producto)
                precio_obj.porcentaje_recargo = recargo
                precio_obj.porcentaje_descuento = descuento
                precio_obj.calcular_y_guardar(save=True)

            messages.success(request, f"Producto '{producto.nombre}' y sus precios actualizados correctamente.")
            return redirect('gestion:productos_list')
    else:
        form = ProductoForm(instance=producto)

    precios_info = []
    for lista in listas_activas:
        p_obj = PrecioProducto.objects.filter(tipo_lista=lista, producto=producto).first()
        precios_info.append({
            'lista': lista,
            'precio_obj': p_obj,
            'recargo': p_obj.porcentaje_recargo if p_obj else Decimal('0.00'),
            'descuento': p_obj.porcentaje_descuento if p_obj else Decimal('0.00'),
            'precio_final': p_obj.precio_final if p_obj else Decimal('0.00'),
        })

    context = {
        'form': form,
        'producto': producto,
        'precios_info': precios_info,
        'titulo': f'Editar Producto: {producto.nombre}'
    }
    return render(request, 'gestion/producto_form.html', context)


# ==============================================================================
# BANDEJA GENERAL DE PEDIDOS
# ==============================================================================

@role_required(['SUPERVISOR', 'ADMIN', 'FACTURACION'])
def pedidos_list_view(request):
    pedidos_qs = Pedido.objects.select_related('cliente', 'vendedor', 'lista_precio').prefetch_related('remitos', 'detalles')

    q = request.GET.get('q', '').strip()
    estado = request.GET.get('estado', '').strip()
    vendedor_id = request.GET.get('vendedor', '').strip()
    desde_str = request.GET.get('desde', '').strip()
    hasta_str = request.GET.get('hasta', '').strip()

    if q:
        pedidos_qs = pedidos_qs.filter(
            Q(numero_pedido__icontains=q) |
            Q(cliente__razon_social__icontains=q) |
            Q(cliente__cuit__icontains=q)
        )

    if estado:
        pedidos_qs = pedidos_qs.filter(estado=estado)

    if vendedor_id and vendedor_id.isdigit():
        pedidos_qs = pedidos_qs.filter(vendedor_id=int(vendedor_id))

    if desde_str:
        try:
            desde_obj = datetime.strptime(desde_str, '%Y-%m-%d').date()
            pedidos_qs = pedidos_qs.filter(fecha_creacion__date__gte=desde_obj)
        except ValueError:
            pass

    if hasta_str:
        try:
            hasta_obj = datetime.strptime(hasta_str, '%Y-%m-%d').date()
            pedidos_qs = pedidos_qs.filter(fecha_creacion__date__lte=hasta_obj)
        except ValueError:
            pass

    context = {
        'pedidos': pedidos_qs.order_by('-fecha_creacion'),
        'vendedores': Vendedor.objects.filter(activo=True),
        'query': q,
        'estado_actual': estado,
        'vendedor_actual': int(vendedor_id) if vendedor_id.isdigit() else None,
        'desde': desde_str,
        'hasta': hasta_str,
    }
    return render(request, 'gestion/pedidos_list.html', context)


# ==============================================================================
# BANDEJA DE EXPEDICIÓN / DEPÓSITO
# ==============================================================================

@login_required
def deposito_pedidos_view(request):
    if not _check_permisos_deposito(request.user):
        return HttpResponseForbidden('Acceso no autorizado al panel de depósito y expedición.')

    pedidos_aprobados = Pedido.objects.filter(estado='APROBADO')\
        .select_related('cliente', 'vendedor', 'lista_precio')\
        .prefetch_related('detalles', 'detalles__producto', 'detalles__presentacion')\
        .order_by('fecha_creacion')

    pedidos_facturados = Pedido.objects.filter(estado__in=['FACTURADO_REMITO', 'FACTURADO'])\
        .select_related('cliente', 'vendedor', 'lista_precio')\
        .prefetch_related('remitos', 'detalles')\
        .order_by('-fecha_creacion')[:30]

    context = {
        'pedidos_aprobados': pedidos_aprobados,
        'pedidos_facturados': pedidos_facturados,
    }
    return render(request, 'gestion/deposito_pedidos.html', context)


# ==============================================================================
# ABM LISTAS DE PRECIOS
# ==============================================================================

@role_required(['SUPERVISOR', 'ADMIN', 'FACTURACION'])
def listas_precio_list_view(request):
    listas = TipoListaPrecio.objects.annotate(cantidad_productos=models.Count('precios_productos')).order_by('nombre')
    context = {
        'listas': listas,
    }
    return render(request, 'gestion/listas_precio_list.html', context)


@role_required(['SUPERVISOR', 'ADMIN', 'FACTURACION'])
def lista_precio_crear_view(request):
    if request.method == 'POST':
        form = ListaPrecioForm(request.POST)
        if form.is_valid():
            lista = form.save()
            messages.success(request, f"Lista de precios '{lista.nombre}' creada exitosamente.")
            return redirect('gestion:listas_precio_list')
    else:
        form = ListaPrecioForm()

    context = {
        'form': form,
        'titulo': 'Crear Lista de Precios'
    }
    return render(request, 'gestion/lista_precio_form.html', context)


@role_required(['SUPERVISOR', 'ADMIN', 'FACTURACION'])
def lista_precio_editar_view(request, lista_id):
    lista = get_object_or_404(TipoListaPrecio, id=lista_id)

    if request.method == 'POST':
        form = ListaPrecioForm(request.POST, instance=lista)
        if form.is_valid():
            lista = form.save()
            messages.success(request, f"Lista de precios '{lista.nombre}' actualizada correctamente.")
            return redirect('gestion:listas_precio_list')
    else:
        form = ListaPrecioForm(instance=lista)

    context = {
        'form': form,
        'lista': lista,
        'titulo': f'Editar Lista de Precios: {lista.nombre}'
    }
    return render(request, 'gestion/lista_precio_form.html', context)


# ==============================================================================
# SIMULADOR INTERACTIVO DE PRECIOS EN VIVO
# ==============================================================================

@role_required(['SUPERVISOR', 'ADMIN', 'FACTURACION'])
def simulador_precios_view(request):
    listas_activas = TipoListaPrecio.objects.filter(activa=True)
    categorias = Categoria.objects.filter(activa=True)
    productos = Producto.objects.filter(activo=True).select_related('categoria', 'marca').order_by('nombre')

    context = {
        'listas_activas': listas_activas,
        'categorias': categorias,
        'productos': productos,
    }
    return render(request, 'gestion/simulador_precios.html', context)
