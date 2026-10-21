from decimal import Decimal
from django.test import TestCase
from django.db import IntegrityError
from django.db.models import ProtectedError
from usuarios.models import Usuario
from geografia.models import Provincia, Localidad, Zona
from clientes.models import Vendedor, AsignacionZonaVendedor, CondicionIVA, Cliente
from productos.models import ListaPrecio


class Modulo2EntidadesMaestrasTestCase(TestCase):
    def setUp(self):
        # 1. Geografía
        self.provincia = Provincia.objects.create(nombre="Misiones")
        self.localidad = Localidad.objects.create(
            provincia=self.provincia,
            nombre="San Vicente",
            codigo_postal="3360"
        )
        self.zona1 = Zona.objects.create(
            nombre="Ruta 14 Centro",
            descripcion="San Vicente a Dos de Mayo",
            dia_reparto_defecto="Lunes y Jueves",
            activa=True
        )
        self.zona2 = Zona.objects.create(
            nombre="Ruta 14 Norte",
            descripcion="San Pedro a Bernardo de Irigoyen",
            dia_reparto_defecto="Martes y Viernes",
            activa=True
        )

        # 2. Vendedores y Usuarios
        self.user_vendedor_a = Usuario.objects.create_user(
            username="vendedor_a",
            cuit_dni="20111111111",
            nombre="Carlos",
            apellido="López",
            rol="VENDEDOR",
            password="Password123!"
        )
        self.vendedor_a = Vendedor.objects.create(
            usuario=self.user_vendedor_a,
            legajo="VEND-001",
            nombre="Carlos",
            apellido="López",
            telefono="3755112233",
            comision_porcentaje=Decimal('5.00'),
            activo=True
        )

        self.user_vendedor_b = Usuario.objects.create_user(
            username="vendedor_b",
            cuit_dni="20222222222",
            nombre="Ana",
            apellido="Martínez",
            rol="VENDEDOR",
            password="Password123!"
        )
        self.vendedor_b = Vendedor.objects.create(
            usuario=self.user_vendedor_b,
            legajo="VEND-002",
            nombre="Ana",
            apellido="Martínez",
            telefono="3755445566",
            comision_porcentaje=Decimal('4.50'),
            activo=True
        )

        self.user_supervisor = Usuario.objects.create_user(
            username="supervisor_gral",
            cuit_dni="20333333333",
            nombre="Marcos",
            apellido="Supervisor",
            rol="SUPERVISOR",
            password="Password123!"
        )

        # 3. Datos comerciales auxiliares
        self.condicion_iva = CondicionIVA.objects.create(
            codigo="RI",
            descripcion="Responsable Inscripto",
            discrimina_iva=True
        )
        self.lista_precio = ListaPrecio.objects.create(
            nombre="Lista 1 - Mayorista",
            activa=True
        )

        # 4. Clientes asociados
        self.cliente_a1 = Cliente.objects.create(
            cuit="30711223344",
            razon_social="Comercial San Vicente SRL",
            nombre_fantasia="Supermercado San Vicente",
            domicilio="Av. Libertador 1234",
            zona=self.zona1,
            vendedor=self.vendedor_a,
            localidad=self.localidad,
            condicion_iva=self.condicion_iva,
            lista_precio_default=self.lista_precio,
            telefono="3755443322",
            telefono_alt="3755998877",
            contacto="Juan Gerente",
            saldo_cta_cte_inicial=Decimal('150000.00'),
            activo=True
        )

        self.cliente_b1 = Cliente.objects.create(
            cuit="30889900112",
            razon_social="Autoservicio Del Norte SA",
            nombre_fantasia="Autoservicio Norte",
            domicilio="Ruta 14 Km 1000",
            zona=self.zona2,
            vendedor=self.vendedor_b,
            localidad=self.localidad,
            condicion_iva=self.condicion_iva,
            lista_precio_default=self.lista_precio,
            saldo_cta_cte_inicial=Decimal('75000.00'),
            activo=True
        )

    def test_creacion_integra_y_claves_foraneas_protegidas(self):
        """
        a) Verifica que Zona, Vendedor y Cliente se creen correctamente y que
        la eliminación de Zona o Vendedor esté protegida ante clientes dependientes (PROTECT).
        """
        self.assertEqual(Cliente.objects.count(), 2)
        self.assertEqual(self.cliente_a1.zona, self.zona1)
        self.assertEqual(self.cliente_a1.vendedor, self.vendedor_a)

        # Intentar eliminar Zona con clientes debe levantar ProtectedError
        with self.assertRaises(ProtectedError):
            self.zona1.delete()

        # Intentar eliminar Vendedor con clientes debe levantar ProtectedError
        with self.assertRaises(ProtectedError):
            self.vendedor_a.delete()

    def test_validacion_unicidad_cuit_cliente(self):
        """
        b) Verifica que no se puedan crear dos clientes con el mismo CUIT.
        """
        with self.assertRaises(IntegrityError):
            Cliente.objects.create(
                cuit="30711223344",  # Mismo CUIT que cliente_a1
                razon_social="Cliente Fantasma SRL",
                domicilio="Calle Falsa 123",
                zona=self.zona1,
                vendedor=self.vendedor_a
            )

    def test_manager_para_usuario_aislamiento_vendedor(self):
        """
        c) Verifica el aislamiento comercial del Manager para_usuario:
        - Vendedor A solo ve sus clientes asignados.
        - Vendedor B solo ve sus clientes asignados.
        - Supervisor tiene visibilidad total de la cartera.
        """
        # Vendedor A
        qs_vendedor_a = Cliente.objects.para_usuario(self.user_vendedor_a)
        self.assertEqual(qs_vendedor_a.count(), 1)
        self.assertIn(self.cliente_a1, qs_vendedor_a)
        self.assertNotIn(self.cliente_b1, qs_vendedor_a)

        # Vendedor B
        qs_vendedor_b = Cliente.objects.para_usuario(self.user_vendedor_b)
        self.assertEqual(qs_vendedor_b.count(), 1)
        self.assertIn(self.cliente_b1, qs_vendedor_b)
        self.assertNotIn(self.cliente_a1, qs_vendedor_b)

        # Supervisor
        qs_supervisor = Cliente.objects.para_usuario(self.user_supervisor)
        self.assertEqual(qs_supervisor.count(), 2)
        self.assertIn(self.cliente_a1, qs_supervisor)
        self.assertIn(self.cliente_b1, qs_supervisor)

    def test_asignacion_dinamica_zonas_vendedor(self):
        asig1 = AsignacionZonaVendedor.objects.create(
            vendedor=self.vendedor_a,
            zona=self.zona1,
            activo=True
        )
        asig2 = AsignacionZonaVendedor.objects.create(
            vendedor=self.vendedor_a,
            zona=self.zona2,
            activo=True
        )

        self.assertEqual(self.vendedor_a.asignaciones_zona.count(), 2)
        asig2.activo = False
        asig2.save()

        zonas_activas = self.vendedor_a.asignaciones_zona.filter(activo=True)
        self.assertEqual(zonas_activas.count(), 1)
        self.assertEqual(zonas_activas.first().zona, self.zona1)
