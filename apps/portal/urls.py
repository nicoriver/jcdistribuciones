from django.urls import path
from . import views

app_name = 'portal'

urlpatterns = [
    # Autenticación
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Portal Cliente
    path('', views.catalogo_view, name='catalogo'),
    path('catalogo/', views.catalogo_view, name='catalogo_alias'),
    path('api/carrito/agregar/', views.agregar_item_carrito_api, name='api_agregar_carrito'),
    path('carrito/', views.carrito_view, name='carrito'),
    path('carrito/item/<int:item_id>/eliminar/', views.eliminar_item_carrito_view, name='eliminar_item_carrito'),
    path('carrito/enviar/', views.enviar_pedido_view, name='enviar_pedido'),
    path('mis-pedidos/', views.mis_pedidos_view, name='mis_pedidos'),
    path('mis-pedidos/<int:pedido_id>/', views.detalle_pedido_view, name='detalle_pedido'),

    # Panel Vendedor / Móvil
    path('vendedor/pedidos/', views.vendedor_pedidos_view, name='vendedor_pedidos'),
    path('vendedor/pedidos/<int:pedido_id>/', views.vendedor_gestionar_pedido_view, name='vendedor_gestionar_pedido'),

    # Pre-Venta Móvil en Calle
    path('vendedor/nuevo-pedido/', views.vendedor_seleccionar_cliente_view, name='vendedor_seleccionar_cliente'),
    path('vendedor/nuevo-pedido/<int:cliente_id>/', views.vendedor_tomar_pedido_view, name='vendedor_tomar_pedido'),
    path('vendedor/api/agregar-item/', views.vendedor_agregar_item_api, name='vendedor_agregar_item_api'),
    path('vendedor/pedidos/<int:pedido_id>/confirmar-preventa/', views.vendedor_confirmar_pedido_view, name='vendedor_confirmar_preventa'),
]
