from django.test import TestCase
from django.db import IntegrityError
from proveedores.models import Proveedor


class ProveedorTestCase(TestCase):
    def test_creacion_proveedor_y_unicidad_cuit(self):
        prov = Proveedor.objects.create(
            cuit="30-55667788-9",
            razon_social="Molinos Río de la Plata",
            domicilio="Av. Industrial 500",
            telefono="011-4567-8900",
            email="ventas@molinos.com.ar",
            contacto_nombre="Martín Gerente",
            activo=True
        )
        self.assertEqual(prov.razon_social, "Molinos Río de la Plata")
        self.assertTrue(prov.activo)
        self.assertIn("30-55667788-9", str(prov))

        # Unicidad de CUIT
        with self.assertRaises(IntegrityError):
            Proveedor.objects.create(
                cuit="30-55667788-9",
                razon_social="Distribuidora Duplicada SRL"
            )
