import json
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime
from functools import wraps
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views import View
from django.contrib import messages
from django.http import HttpResponseForbidden, HttpResponseBadRequest, HttpResponseNotAllowed
from django.db import models
from django.db.models import Q, F, Sum
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.urls import reverse
from django.core.paginator import Paginator

from clientes.models import Cliente, Vendedor, AsignacionZonaVendedor, CondicionIVA
from geografia.models import Zona, Localidad, Provincia
from productos.models import Producto, Presentacion, Categoria, Marca, TipoListaPrecio, ListaPrecio, PrecioProducto
from pedidos.models import Pedido
from pedidos.services import PedidoService
from compras.models import Compra
from proveedores.models import Proveedor
from comprobantes.models import Remito
from comprobantes.services import RemitoService
from .forms import (
    ClienteForm, ProductoForm, PrecioProductoForm, ListaPrecioForm,
    ZonaForm, VendedorForm, ProveedorForm
)


def _get_query_string(request):
    """Auxiliar para preservar filtros en enlaces de paginación."""
    params = request.GET.copy()
    params.pop('page', None)
    return params.urlencode()


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


def _get_remito_directo_context(cliente_id=None, tipo_lista_precio_id=None, fecha_val=None, observaciones='', filas=None):
    clientes = Cliente.objects.filter(activo=True).select_related('vendedor', 'zona', 'tipo_lista_precio').order_by('razon_social')
    listas_precio = TipoListaPrecio.objects.filter(activa=True).order_by('nombre')

    minorista_qs = TipoListaPrecio.objects.filter(activa=True, nombre__iexact='Minorista')
    if minorista_qs.count() == 1:
        default_lista = minorista_qs.first()
    else:
        minorista_qs = TipoListaPrecio.objects.filter(activa=True, nombre__icontains='minorista')
        if minorista_qs.count() == 1:
            default_lista = minorista_qs.first()
        else:
            default_lista = None

    selected_lista_id = tipo_lista_precio_id
    if not selected_lista_id and default_lista:
        selected_lista_id = default_lista.id

    fecha_hoy = fecha_val or timezone.localdate().isoformat()

    productos_qs = (
        Producto.objects.filter(activo=True)
        .select_related('categoria', 'marca')
        .prefetch_related('presentaciones', 'precios', 'precios__tipo_lista')
        .order_by('nombre')
    )

    catalog_data = {}
    for p in productos_qs:
        presentaciones_list = [
            {
                'id': pres.id,
                'nombre': pres.nombre,
                'factor': pres.factor_conversion,
                'es_default': pres.es_default
            }
            for pres in p.presentaciones.all()
        ]
        if not presentaciones_list:
            presentaciones_list = [{
                'id': '',
                'nombre': 'Unidad Base (x1)',
                'factor': 1,
                'es_default': True
            }]
        elif not any(x['es_default'] for x in presentaciones_list):
            presentaciones_list[0]['es_default'] = True

        precios_dict = {
            str(pr.tipo_lista_id): str(pr.precio_final)
            for pr in p.precios.all()
            if pr.tipo_lista_id
        }

        catalog_data[str(p.codigo).strip()] = {
            'id': p.id,
            'codigo': str(p.codigo).strip(),
            'nombre': p.nombre,
            'categoria': p.categoria.nombre if p.categoria else '',
            'marca': p.marca.nombre if p.marca else '',
            'stock': p.stock_actual,
            'presentaciones': presentaciones_list,
            'precios': precios_dict
        }

    return {
        'clientes': clientes,
        'listas_precio': listas_precio,
        'default_lista': default_lista,
        'selected_lista_id': int(selected_lista_id) if selected_lista_id and str(selected_lista_id).isdigit() else None,
        'selected_cliente_id': int(cliente_id) if cliente_id and str(cliente_id).isdigit() else None,
        'fecha_seleccionada': fecha_hoy,
        'observaciones': observaciones or '',
        'filas_recargadas': filas or [],
        'catalog_data': catalog_data,
        'catalog_list': list(catalog_data.values()),
    }


@method_decorator(role_required(['SUPERVISOR', 'ADMIN', 'FACTURACION']), name='dispatch')
class VentaDirectaRemitoView(View):
    """
    Formulario interactivo (/gestion/remito-directo/) para emitir un Remito A4
    sin pedido previo (venta directa de mostrador / despacho inmediato).
    Optimizado para carga por teclado con recorrido por tecla Enter.
    """
    template_name = 'gestion/remito_directo.html'

    def get(self, request):
        context = _get_remito_directo_context()
        return render(request, self.template_name, context)

    def post(self, request):
        cliente_id = request.POST.get('cliente_id')
        fecha_str = request.POST.get('fecha') or timezone.localdate().isoformat()
        tipo_lista_precio_id = request.POST.get('tipo_lista_precio_id')
        observaciones = request.POST.get('observaciones', '').strip()

        codigos = request.POST.getlist('codigo[]') or request.POST.getlist('codigo')
        prod_ids = request.POST.getlist('producto_id[]') or request.POST.getlist('producto_id')
        pres_ids = request.POST.getlist('presentacion_id[]') or request.POST.getlist('presentacion_id')
        cantidades = request.POST.getlist('cantidad[]') or request.POST.getlist('cantidad')
        descuentos = (
            request.POST.getlist('porcentaje_descuento[]')
            or request.POST.getlist('descuento_porcentaje[]')
            or request.POST.getlist('porcentaje_descuento')
        )
        precios = request.POST.getlist('precio_unitario[]') or request.POST.getlist('precio_unitario')

        max_rows = max(len(codigos), len(prod_ids), len(cantidades), len(descuentos), len(precios), 0)
        filas_recargadas = []
        errores_filas = []
        items_data = []

        # 1. Validación de Cliente
        cliente = None
        if cliente_id and str(cliente_id).isdigit():
            cliente = Cliente.objects.filter(id=int(cliente_id), activo=True).select_related('vendedor', 'tipo_lista_precio').first()

        if not cliente:
            messages.error(request, "Debe seleccionar un cliente activo válido.")

        # 2. Vendedor: resuelto de la ficha del cliente (opcional, sin bloqueo si es nulo)
        vendedor = getattr(cliente, 'vendedor', None) if cliente else None

        # 3. Validación de Lista de Precios (Estricta y Exclusiva: no sustituir silenciosamente)
        tipo_lista = None
        if tipo_lista_precio_id and str(tipo_lista_precio_id).isdigit():
            tipo_lista = TipoListaPrecio.objects.filter(id=int(tipo_lista_precio_id), activa=True).first()

        if not tipo_lista:
            messages.error(request, "Debe seleccionar una lista de precios activa válida.")

        # 4. Procesar y validar renglones
        for idx in range(max_rows):
            codigo_val = codigos[idx].strip() if idx < len(codigos) else ''
            p_id_val = prod_ids[idx].strip() if idx < len(prod_ids) else ''
            pres_id_val = pres_ids[idx].strip() if idx < len(pres_ids) else ''
            cant_val = cantidades[idx].strip() if idx < len(cantidades) else ''
            desc_val = descuentos[idx].strip() if idx < len(descuentos) else ''

            # Fila vacía con valores iniciales por defecto -> ignorar consistentemente sin bloquear
            is_empty_initial = (
                not codigo_val
                and not p_id_val
                and cant_val in ('', '1')
                and (not desc_val or desc_val.replace(',', '.') in ('0', '0.0', '0.00'))
            )
            if is_empty_initial:
                continue

            fila_dict = {
                'codigo': codigo_val,
                'producto_id': p_id_val,
                'presentacion_id': pres_id_val,
                'cantidad': cant_val,
                'descuento': desc_val or '0.00',
            }
            filas_recargadas.append(fila_dict)

            # Fila incompleta sin producto ni código
            if not p_id_val and not codigo_val:
                errores_filas.append(f"Renglón #{idx+1}: Incompleto. Ingrese el código del producto.")
                continue

            # Resolución y coherencia estricta entre código e ID
            prod_by_code = None
            if codigo_val:
                prod_by_code = Producto.objects.filter(codigo__iexact=codigo_val, activo=True).first()

            prod_by_id = None
            if p_id_val and p_id_val.isdigit():
                prod_by_id = Producto.objects.filter(id=int(p_id_val), activo=True).first()

            if codigo_val and p_id_val:
                if not prod_by_code or not prod_by_id or prod_by_code.id != prod_by_id.id:
                    errores_filas.append(
                        f"Renglón #{idx+1}: Incoherencia entre el código '{codigo_val}' y el producto seleccionado."
                    )
                    continue
                producto = prod_by_code
            elif prod_by_code:
                producto = prod_by_code
            elif prod_by_id:
                producto = prod_by_id
            else:
                errores_filas.append(f"Renglón #{idx+1}: El producto con código '{codigo_val}' no existe o se encuentra inactivo.")
                continue

            if not producto:
                errores_filas.append(f"Renglón #{idx+1}: El producto con código '{codigo_val}' no existe o se encuentra inactivo.")
                continue

            # Validación de Presentación: rechazar si no existe o no pertenece al producto
            presentacion = None
            factor_unidades = 1
            if pres_id_val and pres_id_val.strip():
                if not pres_id_val.isdigit():
                    errores_filas.append(f"Renglón #{idx+1} ({producto.nombre}): Identificador de presentación inválido.")
                    continue
                presentacion = Presentacion.objects.filter(id=int(pres_id_val), producto=producto).first()
                if not presentacion:
                    errores_filas.append(
                        f"Renglón #{idx+1} ({producto.nombre}): La presentación especificada no existe o no pertenece a este producto."
                    )
                    continue
                factor_unidades = int(presentacion.factor_conversion)

            if not cant_val:
                errores_filas.append(f"Renglón #{idx+1} ({producto.nombre}): Debe ingresar una cantidad.")
                continue

            try:
                cant_dec = Decimal(str(cant_val).replace(',', '.'))
            except Exception:
                errores_filas.append(f"Renglón #{idx+1} ({producto.nombre}): Cantidad inválida '{cant_val}'.")
                continue

            if cant_dec <= Decimal('0'):
                errores_filas.append(f"Renglón #{idx+1} ({producto.nombre}): La cantidad debe ser mayor a 0.")
                continue

            if cant_dec % Decimal('1') != Decimal('0'):
                errores_filas.append(
                    f"Renglón #{idx+1} ({producto.nombre}): La cantidad debe ser un número entero (se ingresó '{cant_val}'). "
                    "No se permiten cantidades fraccionarias."
                )
                continue

            cantidad_int = int(cant_dec)

            try:
                desc_str = desc_val.replace(',', '.') if desc_val else '0.00'
                desc_dec = Decimal(desc_str)
            except Exception:
                errores_filas.append(f"Renglón #{idx+1} ({producto.nombre}): Porcentaje de descuento inválido '{desc_val}'.")
                continue

            if desc_dec < Decimal('0.00') or desc_dec > Decimal('100.00'):
                errores_filas.append(f"Renglón #{idx+1} ({producto.nombre}): El descuento ({desc_dec}%) debe estar entre 0 y 100.")
                continue

            # Resolución de precio: Exclusivamente resuelto en el servidor desde la lista de precios activa
            if not tipo_lista:
                errores_filas.append(f"Renglón #{idx+1}: Debe seleccionar una lista de precios activa para resolver el precio.")
                continue

            precio_lista = PrecioProducto.objects.filter(producto=producto, tipo_lista=tipo_lista).first()
            if not precio_lista:
                errores_filas.append(
                    f"Renglón #{idx+1}: El producto '{producto.nombre}' [{producto.codigo}] no tiene precio definido en la lista '{tipo_lista.nombre}'."
                )
                continue

            precio_unitario = (precio_lista.precio_final * Decimal(factor_unidades)).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )

            items_data.append({
                'producto': producto,
                'presentacion': presentacion,
                'factor_unidades': factor_unidades,
                'cantidad': cantidad_int,
                'porcentaje_descuento': desc_dec,
                'precio_unitario_historico': precio_unitario,
            })

        for err in errores_filas:
            messages.error(request, err)

        if not errores_filas and not items_data:
            messages.error(request, "Debe cargar al menos un producto válido para emitir el remito.")

        # Si hubo cualquier error, re-renderizar preservando intacta la cabecera y filas
        if not cliente or not tipo_lista or errores_filas or not items_data:
            context = _get_remito_directo_context(
                cliente_id=cliente_id,
                tipo_lista_precio_id=tipo_lista_precio_id,
                fecha_val=fecha_str,
                observaciones=observaciones,
                filas=filas_recargadas
            )
            return render(request, self.template_name, context)

        # 5. Emisión transaccional vía RemitoService
        try:
            remito = RemitoService.emitir_remito(
                cliente=cliente,
                vendedor=vendedor,
                supervisor=request.user,
                items=items_data,
                fecha=fecha_str,
                tipo_lista_precio=tipo_lista,
                observaciones=observaciones
            )
            messages.success(request, f"Remito directo {remito.numero_completo} emitido correctamente.")
            return redirect('comprobantes:imprimir_remito', remito_id=remito.id)
        except Exception as e:
            messages.error(request, f"Error al emitir el remito directo: {str(e)}")
            context = _get_remito_directo_context(
                cliente_id=cliente_id,
                tipo_lista_precio_id=tipo_lista_precio_id,
                fecha_val=fecha_str,
                observaciones=observaciones,
                filas=filas_recargadas
            )
            return render(request, self.template_name, context)


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

    if vendedor_id == 'sin_vendedor':
        clientes_qs = clientes_qs.filter(vendedor__isnull=True)
    elif vendedor_id and vendedor_id.isdigit():
        clientes_qs = clientes_qs.filter(vendedor_id=int(vendedor_id))

    if zona_id == 'sin_zona':
        clientes_qs = clientes_qs.filter(zona__isnull=True)
    elif zona_id and zona_id.isdigit():
        clientes_qs = clientes_qs.filter(zona_id=int(zona_id))

    if estado:
        clientes_qs = clientes_qs.filter(estado=estado)

    paginator = Paginator(clientes_qs.order_by('razon_social'), 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'clientes': page_obj,
        'vendedores': Vendedor.objects.filter(activo=True),
        'zonas': Zona.objects.all(),
        'query': q,
        'vendedor_actual': int(vendedor_id) if vendedor_id.isdigit() else (vendedor_id if vendedor_id == 'sin_vendedor' else None),
        'zona_actual': int(zona_id) if zona_id.isdigit() else (zona_id if zona_id == 'sin_zona' else None),
        'estado_actual': estado,
        'query_string': _get_query_string(request),
    }
    return render(request, 'gestion/clientes_list.html', context)


def _obtener_dependencias_cliente():
    faltantes = []
    if not CondicionIVA.objects.exists():
        faltantes.append({'nombre': 'Condiciones de IVA', 'url': '/admin/clientes/condicioniva/', 'admin': True})
    if not TipoListaPrecio.objects.filter(activa=True).exists():
        faltantes.append({'nombre': 'Listas de Precios', 'url': '/gestion/listas-precio/nueva/', 'admin': False})
    if not Zona.objects.filter(activa=True).exists():
        faltantes.append({'nombre': 'Zonas de Reparto', 'url': '/gestion/zonas/nueva/', 'admin': False})
    if not Localidad.objects.exists():
        faltantes.append({'nombre': 'Localidades', 'url': '/admin/geografia/localidad/', 'admin': True})
    return faltantes


@role_required(['SUPERVISOR', 'ADMIN', 'FACTURACION'])
def cliente_crear_view(request):
    if request.method == 'POST':
        form = ClienteForm(request.POST)
        if form.is_valid():
            cliente = form.save()
            if getattr(form, 'usuario_creado', False):
                if getattr(form, 'password_generada', None):
                    messages.success(
                        request,
                        f"Cliente '{cliente.razon_social}' registrado con usuario del portal '{cliente.usuario.username}'. "
                        f"Contraseña inicial generada: {form.password_generada} (comuníquela al cliente)."
                    )
                else:
                    messages.success(
                        request,
                        f"Cliente '{cliente.razon_social}' registrado con usuario del portal '{cliente.usuario.username}'."
                    )
            else:
                messages.success(request, f"Cliente '{cliente.razon_social}' registrado exitosamente.")
            return redirect('gestion:clientes_list')
    else:
        form = ClienteForm()

    context = {
        'form': form,
        'dependencias_faltantes': _obtener_dependencias_cliente(),
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
            if getattr(form, 'usuario_creado', False):
                if getattr(form, 'password_generada', None):
                    messages.success(
                        request,
                        f"Cliente '{cliente.razon_social}' actualizado. Se habilitó acceso al portal: "
                        f"Usuario '{cliente.usuario.username}' | Contraseña temporal: {form.password_generada} (comuníquela al cliente)."
                    )
                else:
                    messages.success(
                        request,
                        f"Cliente '{cliente.razon_social}' actualizado con acceso al portal (Usuario '{cliente.usuario.username}')."
                    )
            elif cliente.usuario and form.cleaned_data.get('password_portal', '').strip():
                messages.success(request, f"Cliente '{cliente.razon_social}' y contraseña del portal actualizados correctamente.")
            else:
                messages.success(request, f"Cliente '{cliente.razon_social}' actualizado correctamente.")
            return redirect('gestion:clientes_list')
    else:
        form = ClienteForm(instance=cliente)

    context = {
        'form': form,
        'cliente': cliente,
        'dependencias_faltantes': _obtener_dependencias_cliente(),
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

    paginator = Paginator(productos_qs.order_by('nombre'), 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'productos': page_obj,
        'categorias': Categoria.objects.filter(activa=True),
        'marcas': Marca.objects.filter(activa=True),
        'listas_precio': TipoListaPrecio.objects.filter(activa=True),
        'query': q,
        'categoria_actual': int(categoria_id) if categoria_id.isdigit() else None,
        'marca_actual': int(marca_id) if marca_id.isdigit() else None,
        'stock_bajo': stock_bajo,
        'query_string': _get_query_string(request),
    }
    return render(request, 'gestion/productos_list.html', context)


def _obtener_dependencias_producto():
    faltantes = []
    if not Categoria.objects.filter(activa=True).exists():
        faltantes.append({'nombre': 'Categorías', 'url': '/admin/productos/categoria/', 'admin': True})
    if not Marca.objects.filter(activa=True).exists():
        faltantes.append({'nombre': 'Marcas', 'url': '/admin/productos/marca/', 'admin': True})
    if not TipoListaPrecio.objects.filter(activa=True).exists():
        faltantes.append({'nombre': 'Listas de Precios', 'url': '/gestion/listas-precio/nueva/', 'admin': False})
    return faltantes


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
        'dependencias_faltantes': _obtener_dependencias_producto(),
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
        'dependencias_faltantes': _obtener_dependencias_producto(),
        'titulo': f'Editar Producto: {producto.nombre}'
    }
    return render(request, 'gestion/producto_form.html', context)


# ==============================================================================
# MÓDULO DE ZONAS LOGÍSTICAS
# ==============================================================================

@role_required(['SUPERVISOR', 'ADMIN'])
def zonas_list_view(request):
    zonas_qs = Zona.objects.annotate(
        total_clientes=models.Count('clientes', distinct=True),
        total_vendedores=models.Count('vendedores', filter=models.Q(asignaciones_vendedor__activo=True), distinct=True)
    ).order_by('nombre')

    q = request.GET.get('q', '').strip()
    estado = request.GET.get('estado', '').strip()

    if q:
        zonas_qs = zonas_qs.filter(
            Q(nombre__icontains=q) |
            Q(descripcion__icontains=q) |
            Q(dia_reparto_defecto__icontains=q)
        )

    if estado == 'activa':
        zonas_qs = zonas_qs.filter(activa=True)
    elif estado == 'inactiva':
        zonas_qs = zonas_qs.filter(activa=False)

    paginator = Paginator(zonas_qs, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'zonas': page_obj,
        'query': q,
        'estado_actual': estado,
        'query_string': _get_query_string(request),
    }
    return render(request, 'gestion/zonas_list.html', context)


@role_required(['SUPERVISOR', 'ADMIN'])
def zona_crear_view(request):
    if request.method == 'POST':
        form = ZonaForm(request.POST)
        if form.is_valid():
            zona = form.save()
            messages.success(request, f"Zona de reparto '{zona.nombre}' creada exitosamente.")
            return redirect('gestion:zonas_list')
    else:
        form = ZonaForm()

    context = {
        'form': form,
        'titulo': 'Registrar Nueva Zona de Reparto'
    }
    return render(request, 'gestion/zona_form.html', context)


@role_required(['SUPERVISOR', 'ADMIN'])
def zona_editar_view(request, zona_id):
    zona = get_object_or_404(Zona, id=zona_id)

    if request.method == 'POST':
        form = ZonaForm(request.POST, instance=zona)
        if form.is_valid():
            zona = form.save()
            messages.success(request, f"Zona de reparto '{zona.nombre}' actualizada correctamente.")
            return redirect('gestion:zonas_list')
    else:
        form = ZonaForm(instance=zona)

    context = {
        'form': form,
        'zona': zona,
        'titulo': f'Editar Zona: {zona.nombre}'
    }
    return render(request, 'gestion/zona_form.html', context)


@role_required(['SUPERVISOR', 'ADMIN'])
def zona_toggle_view(request, zona_id):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'], 'Acción no permitida vía GET.')

    zona = get_object_or_404(Zona, id=zona_id)
    zona.activa = not zona.activa
    zona.save(update_fields=['activa'])
    estado_str = "activada" if zona.activa else "desactivada"
    messages.info(request, f"Zona '{zona.nombre}' {estado_str} exitosamente.")
    return redirect('gestion:zonas_list')


# ==============================================================================
# MÓDULO DE VENDEDORES Y ASIGNACIÓN DE ZONAS
# ==============================================================================

@role_required(['SUPERVISOR', 'ADMIN'])
def vendedores_list_view(request):
    vendedores_qs = Vendedor.objects.select_related('usuario').prefetch_related(
        'asignaciones_zona',
        'asignaciones_zona__zona'
    ).annotate(
        total_clientes=models.Count('clientes', distinct=True)
    ).order_by('apellido', 'nombre')

    q = request.GET.get('q', '').strip()
    estado = request.GET.get('estado', '').strip()
    zona_id = request.GET.get('zona', '').strip()

    if q:
        vendedores_qs = vendedores_qs.filter(
            Q(nombre__icontains=q) |
            Q(apellido__icontains=q) |
            Q(legajo__icontains=q) |
            Q(dni__icontains=q)
        )

    if estado == 'activo':
        vendedores_qs = vendedores_qs.filter(activo=True)
    elif estado == 'inactivo':
        vendedores_qs = vendedores_qs.filter(activo=False)

    if zona_id and zona_id.isdigit():
        vendedores_qs = vendedores_qs.filter(
            asignaciones_zona__zona_id=int(zona_id),
            asignaciones_zona__activo=True
        )

    paginator = Paginator(vendedores_qs, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'vendedores': page_obj,
        'zonas': Zona.objects.filter(activa=True),
        'query': q,
        'estado_actual': estado,
        'zona_actual': int(zona_id) if zona_id.isdigit() else None,
        'query_string': _get_query_string(request),
    }
    return render(request, 'gestion/vendedores_list.html', context)


@role_required(['SUPERVISOR', 'ADMIN'])
def vendedor_crear_view(request):
    if request.method == 'POST':
        form = VendedorForm(request.POST)
        if form.is_valid():
            vendedor = form.save()
            messages.success(request, f"Vendedor '{vendedor.nombre_completo()}' registrado exitosamente.")
            return redirect('gestion:vendedores_list')
    else:
        form = VendedorForm()

    context = {
        'form': form,
        'titulo': 'Registrar Nuevo Vendedor'
    }
    return render(request, 'gestion/vendedor_form.html', context)


@role_required(['SUPERVISOR', 'ADMIN'])
def vendedor_editar_view(request, vendedor_id):
    vendedor = get_object_or_404(Vendedor, id=vendedor_id)

    if request.method == 'POST':
        form = VendedorForm(request.POST, instance=vendedor)
        if form.is_valid():
            vendedor = form.save()
            messages.success(request, f"Vendedor '{vendedor.nombre_completo()}' actualizado correctamente.")
            return redirect('gestion:vendedores_list')
    else:
        form = VendedorForm(instance=vendedor)

    context = {
        'form': form,
        'vendedor': vendedor,
        'titulo': f'Editar Vendedor: {vendedor.nombre_completo()}'
    }
    return render(request, 'gestion/vendedor_form.html', context)


@role_required(['SUPERVISOR', 'ADMIN'])
def vendedor_toggle_view(request, vendedor_id):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'], 'Acción no permitida vía GET.')

    vendedor = get_object_or_404(Vendedor, id=vendedor_id)
    vendedor.activo = not vendedor.activo
    vendedor.save(update_fields=['activo'])
    estado_str = "activado" if vendedor.activo else "desactivado"
    messages.info(request, f"Vendedor '{vendedor.nombre_completo()}' {estado_str} exitosamente.")
    return redirect('gestion:vendedores_list')


# ==============================================================================
# MÓDULO DE PROVEEDORES
# ==============================================================================

@role_required(['SUPERVISOR', 'ADMIN'])
def proveedores_list_view(request):
    proveedores_qs = Proveedor.objects.annotate(
        total_compras=models.Count('compras', distinct=True),
        total_productos=models.Count('productos', distinct=True)
    ).order_by('razon_social')

    q = request.GET.get('q', '').strip()
    estado = request.GET.get('estado', '').strip()

    if q:
        proveedores_qs = proveedores_qs.filter(
            Q(razon_social__icontains=q) |
            Q(cuit__icontains=q) |
            Q(contacto_nombre__icontains=q) |
            Q(telefono__icontains=q) |
            Q(email__icontains=q)
        )

    if estado == 'activo':
        proveedores_qs = proveedores_qs.filter(activo=True)
    elif estado == 'inactivo':
        proveedores_qs = proveedores_qs.filter(activo=False)

    paginator = Paginator(proveedores_qs, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'proveedores': page_obj,
        'query': q,
        'estado_actual': estado,
        'query_string': _get_query_string(request),
    }
    return render(request, 'gestion/proveedores_list.html', context)


@role_required(['SUPERVISOR', 'ADMIN'])
def proveedor_crear_view(request):
    if request.method == 'POST':
        form = ProveedorForm(request.POST)
        if form.is_valid():
            proveedor = form.save()
            messages.success(request, f"Proveedor '{proveedor.razon_social}' creado exitosamente.")
            return redirect('gestion:proveedores_list')
    else:
        form = ProveedorForm()

    context = {
        'form': form,
        'titulo': 'Registrar Nuevo Proveedor'
    }
    return render(request, 'gestion/proveedor_form.html', context)


@role_required(['SUPERVISOR', 'ADMIN'])
def proveedor_editar_view(request, proveedor_id):
    proveedor = get_object_or_404(Proveedor, id=proveedor_id)

    if request.method == 'POST':
        form = ProveedorForm(request.POST, instance=proveedor)
        if form.is_valid():
            proveedor = form.save()
            messages.success(request, f"Proveedor '{proveedor.razon_social}' actualizado correctamente.")
            return redirect('gestion:proveedores_list')
    else:
        form = ProveedorForm(instance=proveedor)

    context = {
        'form': form,
        'proveedor': proveedor,
        'titulo': f'Editar Proveedor: {proveedor.razon_social}'
    }
    return render(request, 'gestion/proveedor_form.html', context)


@role_required(['SUPERVISOR', 'ADMIN'])
def proveedor_toggle_view(request, proveedor_id):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'], 'Acción no permitida vía GET.')

    proveedor = get_object_or_404(Proveedor, id=proveedor_id)
    proveedor.activo = not proveedor.activo
    proveedor.save(update_fields=['activo'])
    estado_str = "activado" if proveedor.activo else "desactivado"
    messages.info(request, f"Proveedor '{proveedor.razon_social}' {estado_str} exitosamente.")
    return redirect('gestion:proveedores_list')


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
