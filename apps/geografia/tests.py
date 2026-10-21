from django.test import TestCase
from django.db import IntegrityError
from geografia.models import Provincia, Localidad, Zona


class GeografiaTestCase(TestCase):
    def test_creacion_provincia_y_localidad(self):
        prov = Provincia.objects.create(nombre="Misiones")
        loc = Localidad.objects.create(provincia=prov, nombre="San Vicente", codigo_postal="3360")
        self.assertEqual(str(prov), "Misiones")
        self.assertEqual(str(loc), "San Vicente (Misiones)")

        # Unicidad de nombre de provincia
        with self.assertRaises(IntegrityError):
            Provincia.objects.create(nombre="Misiones")

    def test_creacion_zona(self):
        zona = Zona.objects.create(
            nombre="Ruta 14 Centro",
            descripcion="San Vicente a Dos de Mayo",
            dia_reparto_defecto="Lunes y Jueves",
            activa=True
        )
        self.assertEqual(str(zona), "Ruta 14 Centro")
        self.assertTrue(zona.activa)
        self.assertEqual(zona.dia_reparto_defecto, "Lunes y Jueves")

        # Unicidad de nombre de zona
        with self.assertRaises(IntegrityError):
            Zona.objects.create(nombre="Ruta 14 Centro")
