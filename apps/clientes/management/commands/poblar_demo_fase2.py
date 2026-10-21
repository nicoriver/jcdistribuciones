from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import transaction
from usuarios.models import Usuario
from clientes.models import (
    Provincia, Localidad, Zona, Vendedor, AsignacionZonaVendedor,
    CondicionIVA, Cliente
)
from productos.models import (
    Categoria, Marca, AlicuotaIVA, Producto, Presentacion,
    ListaPrecio, PrecioProducto
)


class Command(BaseCommand):
    help = 'Poblar base de datos con datos demo reales para la Fase 2 de JC Distribuciones'

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('--- Iniciando Seed de Datos Demo Fase 2 ---'))

        # 1. Superusuario Admin
        admin_user, created = Usuario.objects.get_or_create(
            username='admin',
            defaults={
                'nombre_completo': 'Administrador General',
                'email': 'admin@jcdistribuciones.com',
                'rol': 'ADMIN',
                'is_staff': True,
                'is_superuser': True,
                'is_active': True
            }
        )
        if created:
            admin_user.set_password('admin1234')
            admin_user.save()
            self.stdout.write(self.style.SUCCESS('[OK] Superusuario admin creado (admin / admin1234)'))
        else:
            self.stdout.write(self.style.WARNING('[INFO] Superusuario admin ya existia'))

        # 2. Alícuotas de IVA
        iva_21, _ = AlicuotaIVA.objects.get_or_create(porcentaje=Decimal('21.00'), defaults={'descripcion': '21% General'})
        iva_105, _ = AlicuotaIVA.objects.get_or_create(porcentaje=Decimal('10.50'), defaults={'descripcion': '10.5% Reducido'})
        iva_0, _ = AlicuotaIVA.objects.get_or_create(porcentaje=Decimal('0.00'), defaults={'descripcion': '0% Exento'})
        self.stdout.write('[OK] Alicuotas de IVA creadas (21%, 10.5%, 0%)')

        # 3. Condiciones de IVA
        cond_ri, _ = CondicionIVA.objects.get_or_create(codigo='RI', defaults={'descripcion': 'Responsable Inscripto', 'discrimina_iva': True})
        cond_cf, _ = CondicionIVA.objects.get_or_create(codigo='CF', defaults={'descripcion': 'Consumidor Final', 'discrimina_iva': False})
        cond_mo, _ = CondicionIVA.objects.get_or_create(codigo='MO', defaults={'descripcion': 'Monotributo', 'discrimina_iva': False})
        self.stdout.write('[OK] Condiciones de IVA creadas (RI, CF, MO)')

        # 4. Geografía (Provincias, Localidades, Zonas)
        prov_misiones, _ = Provincia.objects.get_or_create(nombre='Misiones')
        prov_corrientes, _ = Provincia.objects.get_or_create(nombre='Corrientes')

        loc_san_vicente, _ = Localidad.objects.get_or_create(provincia=prov_misiones, nombre='San Vicente', defaults={'codigo_postal': '3360'})
        loc_dos_de_mayo, _ = Localidad.objects.get_or_create(provincia=prov_misiones, nombre='Dos de Mayo', defaults={'codigo_postal': '3364'})
        loc_obera, _ = Localidad.objects.get_or_create(provincia=prov_misiones, nombre='Obera', defaults={'codigo_postal': '3360'})

        zona_r14, _ = Zona.objects.get_or_create(nombre='Ruta 14 Centro', defaults={'descripcion': 'Tramo San Vicente - Dos de Mayo'})
        zona_urbana, _ = Zona.objects.get_or_create(nombre='Zona Urbana San Vicente', defaults={'descripcion': 'Comercios dentro del casco urbano'})
        self.stdout.write('[OK] Provincias, Localidades y Zonas creadas')

        # 5. Vendedores y Asignación de Zonas
        u_vendedor1, _ = Usuario.objects.get_or_create(
            username='clopez',
            defaults={'nombre_completo': 'Carlos Lopez', 'rol': 'VENDEDOR', 'is_active': True}
        )
        if not u_vendedor1.password:
            u_vendedor1.set_password('vendedor123')
            u_vendedor1.save()

        vendedor1, _ = Vendedor.objects.get_or_create(
            usuario=u_vendedor1,
            defaults={'nombre': 'Carlos', 'apellido': 'Lopez', 'dni': '30111222', 'telefono': '3755123456', 'comision_porcentaje': Decimal('4.50')}
        )
        AsignacionZonaVendedor.objects.get_or_create(vendedor=vendedor1, zona=zona_r14, defaults={'activo': True})
        AsignacionZonaVendedor.objects.get_or_create(vendedor=vendedor1, zona=zona_urbana, defaults={'activo': True})

        u_vendedor2, _ = Usuario.objects.get_or_create(
            username='amartinez',
            defaults={'nombre_completo': 'Ana Martinez', 'rol': 'VENDEDOR', 'is_active': True}
        )
        if not u_vendedor2.password:
            u_vendedor2.set_password('vendedor123')
            u_vendedor2.save()

        vendedor2, _ = Vendedor.objects.get_or_create(
            usuario=u_vendedor2,
            defaults={'nombre': 'Ana', 'apellido': 'Martinez', 'dni': '32333444', 'telefono': '3755987654', 'comision_porcentaje': Decimal('5.00')}
        )
        AsignacionZonaVendedor.objects.get_or_create(vendedor=vendedor2, zona=zona_r14, defaults={'activo': True})
        self.stdout.write('[OK] Vendedores y asignacion de zonas configurados')

        # 6. Lista de Precios
        lista_mayorista, _ = ListaPrecio.objects.get_or_create(
            nombre='Lista 1 - Mayorista',
            defaults={'descripcion': 'Lista general para comercios y distribuidores', 'activa': True}
        )
        self.stdout.write('[OK] Lista de precios "Lista 1 - Mayorista" creada')

        # 7. Clientes y Usuarios de Portal
        u_cliente1, _ = Usuario.objects.get_or_create(
            cuit='30711223344',
            defaults={'nombre_completo': 'Comercial San Vicente SRL', 'email': 'comercial@sanvicente.com', 'rol': 'CLIENTE', 'is_active': True}
        )
        if not u_cliente1.password:
            u_cliente1.set_password('cliente123')
            u_cliente1.save()

        cliente1, _ = Cliente.objects.get_or_create(
            usuario=u_cliente1,
            defaults={
                'razon_social': 'Comercial San Vicente SRL',
                'nombre_fantasia': 'Supermercado El Sol',
                'cuit': '30711223344',
                'condicion_iva': cond_ri,
                'domicilio': 'Av. Tejeda 450',
                'localidad': loc_san_vicente,
                'zona': zona_r14,
                'dia_reparto': 1,  # Lunes
                'vendedor': vendedor1,
                'lista_precio_default': lista_mayorista,
                'telefono': '3755441122',
                'email': 'comercial@sanvicente.com',
                'estado': 'ACTIVO',
                'monto_minimo_pedido': Decimal('40000.00')
            }
        )

        u_cliente2, _ = Usuario.objects.get_or_create(
            cuit='20284445556',
            defaults={'nombre_completo': 'Autoservicio Misiones', 'email': 'autoservicio@misiones.com', 'rol': 'CLIENTE', 'is_active': True}
        )
        if not u_cliente2.password:
            u_cliente2.set_password('cliente123')
            u_cliente2.save()

        cliente2, _ = Cliente.objects.get_or_create(
            usuario=u_cliente2,
            defaults={
                'razon_social': 'Juan Perez - Autoservicio Misiones',
                'nombre_fantasia': 'Autoservicio Misiones',
                'cuit': '20284445556',
                'condicion_iva': cond_mo,
                'domicilio': 'Calle Belgrano 120',
                'localidad': loc_dos_de_mayo,
                'zona': zona_urbana,
                'dia_reparto': 3,  # Miércoles
                'vendedor': vendedor2,
                'lista_precio_default': lista_mayorista,
                'telefono': '3755889900',
                'email': 'autoservicio@misiones.com',
                'estado': 'ACTIVO',
                'monto_minimo_pedido': Decimal('25000.00')
            }
        )
        self.stdout.write('[OK] 2 Clientes de prueba vinculados a usuarios portal')

        # 8. Categorías y Marcas
        cat_bebidas, _ = Categoria.objects.get_or_create(nombre='Bebidas', defaults={'activo': True})
        cat_almacen, _ = Categoria.objects.get_or_create(nombre='Almacen', defaults={'activo': True})

        marca_coca, _ = Marca.objects.get_or_create(nombre='Coca Cola', defaults={'activo': True})
        marca_quilmes, _ = Marca.objects.get_or_create(nombre='Quilmes', defaults={'activo': True})
        marca_arcor, _ = Marca.objects.get_or_create(nombre='Arcor', defaults={'activo': True})

        # 9. Productos, Presentaciones y Precios en Lista
        productos_data = [
            {
                'codigo': 'BEB-001',
                'codigo_barra': '7790895000997',
                'nombre': 'Gaseosa Coca Cola 2.25L',
                'categoria': cat_bebidas,
                'marca': marca_coca,
                'alicuota_iva': iva_21,
                'costo': Decimal('1800.00'),
                'recargo': Decimal('35.00'),
                'descuento': Decimal('5.00'),
                'presentaciones': [('Unidad', Decimal('1.00')), ('Pack x6', Decimal('6.00'))]
            },
            {
                'codigo': 'BEB-002',
                'codigo_barra': '7790070411059',
                'nombre': 'Cerveza Quilmes 1L Retornable',
                'categoria': cat_bebidas,
                'marca': marca_quilmes,
                'alicuota_iva': iva_21,
                'costo': Decimal('1500.00'),
                'recargo': Decimal('40.00'),
                'descuento': Decimal('0.00'),
                'presentaciones': [('Unidad', Decimal('1.00')), ('Cajon x12', Decimal('12.00'))]
            },
            {
                'codigo': 'ALM-001',
                'codigo_barra': '7790040921014',
                'nombre': 'Aceite de Girasol Arcor 900ml',
                'categoria': cat_almacen,
                'marca': marca_arcor,
                'alicuota_iva': iva_21,
                'costo': Decimal('1200.00'),
                'recargo': Decimal('30.00'),
                'descuento': Decimal('2.50'),
                'presentaciones': [('Unidad', Decimal('1.00')), ('Caja x15', Decimal('15.00'))]
            },
            {
                'codigo': 'ALM-002',
                'codigo_barra': '7790040925555',
                'nombre': 'Galletitas Mana Vainilla 145g',
                'categoria': cat_almacen,
                'marca': marca_arcor,
                'alicuota_iva': iva_21,
                'costo': Decimal('600.00'),
                'recargo': Decimal('45.00'),
                'descuento': Decimal('10.00'),
                'presentaciones': [('Unidad', Decimal('1.00')), ('Pack x3', Decimal('3.00')), ('Bulto x24', Decimal('24.00'))]
            }
        ]

        for pdata in productos_data:
            producto, _ = Producto.objects.get_or_create(
                codigo=pdata['codigo'],
                defaults={
                    'codigo_barra': pdata['codigo_barra'],
                    'nombre': pdata['nombre'],
                    'categoria': pdata['categoria'],
                    'marca': pdata['marca'],
                    'alicuota_iva': pdata['alicuota_iva'],
                    'costo': pdata['costo'],
                    'stock_actual': Decimal('200.00'),
                    'punto_reposicion': Decimal('30.00'),
                    'controla_stock': True,
                    'activo': True
                }
            )

            # Presentaciones
            for pres_nombre, pres_factor in pdata['presentaciones']:
                Presentacion.objects.get_or_create(
                    producto=producto,
                    nombre=pres_nombre,
                    defaults={'factor_unidades': pres_factor, 'es_default': (pres_factor == Decimal('1.00'))}
                )

            # Precios en Lista Mayorista
            precio_obj, _ = PrecioProducto.objects.get_or_create(
                lista=lista_mayorista,
                producto=producto,
                defaults={
                    'recargo_porcentaje': pdata['recargo'],
                    'descuento_porcentaje': pdata['descuento']
                }
            )
            precio_obj.calcular_y_guardar(save=True)

        self.stdout.write('[OK] 4 Productos con presentaciones y precios calculados')

        # Resumen Final
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('====================================================='))
        self.stdout.write(self.style.SUCCESS(' DEMO FASE 2 POBLADA CORRECTAMENTE EN LA BASE'))
        self.stdout.write(self.style.SUCCESS('====================================================='))
        self.stdout.write('Credenciales de Acceso Creadas:')
        self.stdout.write('  - Admin Django:   username: admin        / pass: admin1234')
        self.stdout.write('  - Vendedor 1:     username: clopez       / pass: vendedor123')
        self.stdout.write('  - Vendedor 2:     username: amartinez    / pass: vendedor123')
        self.stdout.write('  - Cliente 1 CUIT: CUIT: 30711223344      / pass: cliente123')
        self.stdout.write('  - Cliente 2 CUIT: CUIT: 20284445556      / pass: cliente123')
        self.stdout.write('=====================================================\n')
