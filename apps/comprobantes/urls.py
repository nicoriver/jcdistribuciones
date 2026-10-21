from django.urls import path
from . import views

app_name = 'comprobantes'

urlpatterns = [
    path('remitos/', views.remitos_list_view, name='remitos_list'),
    path('remitos/nuevo/', views.remito_crear_directo_view, name='remito_crear_directo'),
    path('remitos/<int:remito_id>/imprimir/', views.RemitoImpresionView.as_view(), name='imprimir_remito_plural'),
    path('remito/<int:remito_id>/imprimir/', views.RemitoImpresionView.as_view(), name='imprimir_remito'),
    path('remitos/<int:pk>/impresion-a4/', views.RemitoImpresionView.as_view(), name='remito_impresion_a4'),
    path('remitos/<int:remito_id>/faltante/', views.registrar_faltante_ncf_view, name='registrar_faltante_ncf'),
    path('remitos/<int:remito_id>/devolucion/', views.registrar_devolucion_nc_view, name='registrar_devolucion_nc'),
    path('pedidos/<int:pedido_id>/emitir-remito/', views.emitir_remito_view, name='emitir_remito'),
    path('notas-credito/<int:nc_id>/imprimir/', views.imprimir_nota_credito_view, name='imprimir_nota_credito'),
]
