from django.urls import path
from . import views

app_name = 'gestion'

urlpatterns = [
    path('', views.DashboardSupervisorView.as_view(), name='dashboard'),
    path('facturacion/', views.BandejaFacturacionView.as_view(), name='bandeja_facturacion'),
    path('facturacion/<int:pedido_id>/facturar/', views.FacturarPedidoActionView.as_view(), name='facturar_pedido'),
    path('pedidos/<int:pedido_id>/facturar/', views.FacturarPedidoActionView.as_view(), name='facturar_pedido_directo'),
    path('remito-directo/', views.VentaDirectaRemitoView.as_view(), name='remito_directo'),
    path('clientes/', views.clientes_list_view, name='clientes_list'),
    path('clientes/nuevo/', views.cliente_crear_view, name='cliente_crear'),
    path('clientes/<int:cliente_id>/editar/', views.cliente_editar_view, name='cliente_editar'),
    path('productos/', views.productos_list_view, name='productos_list'),
    path('productos/nuevo/', views.producto_crear_view, name='producto_crear'),
    path('productos/<int:producto_id>/editar/', views.producto_editar_view, name='producto_editar'),
    path('pedidos/', views.pedidos_list_view, name='pedidos_list'),
    path('deposito/', views.deposito_pedidos_view, name='deposito_pedidos'),
    path('listas-precio/', views.listas_precio_list_view, name='listas_precio_list'),
    path('listas-precio/nueva/', views.lista_precio_crear_view, name='lista_precio_crear'),
    path('listas-precio/<int:lista_id>/editar/', views.lista_precio_editar_view, name='lista_precio_editar'),
    path('simulador-precios/', views.simulador_precios_view, name='simulador_precios'),
]
