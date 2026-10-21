from datetime import datetime
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from clientes.models import Zona, Cliente
from .services import LogisticaService


def _check_permisos_reportes(user):
    return user.rol in ['ADMIN', 'SUPERVISOR', 'FACTURACION', 'DEPOSITO'] or user.is_staff or user.is_superuser


@login_required
def hoja_ruta_view(request):
    if not _check_permisos_reportes(request.user):
        return HttpResponseForbidden('Acceso no autorizado a reportes de logística.')

    zona_id = request.GET.get('zona', '').strip()
    dia_id = request.GET.get('dia', '').strip()
    fecha_str = request.GET.get('fecha', '').strip()

    fecha_obj = None
    if fecha_str:
        try:
            fecha_obj = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        except ValueError:
            pass

    remitos = LogisticaService.obtener_remitos_para_reparto(
        dia_semana=int(dia_id) if dia_id.isdigit() else None,
        zona_id=int(zona_id) if zona_id.isdigit() else None,
        fecha=fecha_obj
    )

    planilla_carga = LogisticaService.generar_planilla_carga(remitos)

    context = {
        'remitos': remitos,
        'planilla_carga': planilla_carga,
        'zonas': Zona.objects.all(),
        'dias_reparto': Cliente.DIAS_REPARTO,
        'zona_actual': int(zona_id) if zona_id.isdigit() else None,
        'dia_actual': int(dia_id) if dia_id.isdigit() else None,
        'fecha_actual': fecha_str
    }
    return render(request, 'reportes/hoja_ruta.html', context)


@login_required
def imprimir_hoja_ruta_view(request):
    if not _check_permisos_reportes(request.user):
        return HttpResponseForbidden('Acceso no autorizado a impresión de hoja de ruta.')

    zona_id = request.GET.get('zona', '').strip()
    dia_id = request.GET.get('dia', '').strip()
    fecha_str = request.GET.get('fecha', '').strip()
    chofer = request.GET.get('chofer', '').strip()

    fecha_obj = None
    if fecha_str:
        try:
            fecha_obj = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        except ValueError:
            pass

    remitos = LogisticaService.obtener_remitos_para_reparto(
        dia_semana=int(dia_id) if dia_id.isdigit() else None,
        zona_id=int(zona_id) if zona_id.isdigit() else None,
        fecha=fecha_obj
    )

    planilla_carga = LogisticaService.generar_planilla_carga(remitos)
    zona_obj = Zona.objects.filter(id=int(zona_id)).first() if zona_id.isdigit() else None

    context = {
        'remitos': remitos,
        'planilla_carga': planilla_carga,
        'zona_obj': zona_obj,
        'chofer': chofer,
        'fecha_str': fecha_str or datetime.now().strftime('%Y-%m-%d')
    }
    return render(request, 'reportes/hoja_ruta_a4.html', context)


@login_required
def reporte_ventas_vendedores_view(request):
    if not _check_permisos_reportes(request.user):
        return HttpResponseForbidden('Acceso no autorizado a reportes comerciales.')

    desde_str = request.GET.get('desde', '').strip()
    hasta_str = request.GET.get('hasta', '').strip()

    desde_obj = datetime.strptime(desde_str, '%Y-%m-%d').date() if desde_str else None
    hasta_obj = datetime.strptime(hasta_str, '%Y-%m-%d').date() if hasta_str else None

    resumen = LogisticaService.obtener_resumen_ventas_vendedor(fecha_desde=desde_obj, fecha_hasta=hasta_obj)

    total_general = sum(r['total_facturado'] for r in resumen)
    comisiones_general = sum(r['comision_estimada'] for r in resumen)

    context = {
        'resumen': resumen,
        'desde': desde_str,
        'hasta': hasta_str,
        'total_general': total_general,
        'comisiones_general': comisiones_general
    }
    return render(request, 'reportes/ventas_vendedores.html', context)
