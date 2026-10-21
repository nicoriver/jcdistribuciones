from django.urls import path
from . import views

app_name = 'reportes'

urlpatterns = [
    path('hoja-ruta/', views.hoja_ruta_view, name='hoja_ruta'),
    path('hoja-ruta/imprimir/', views.imprimir_hoja_ruta_view, name='imprimir_hoja_ruta'),
    path('ventas-vendedores/', views.reporte_ventas_vendedores_view, name='ventas_vendedores'),
]
