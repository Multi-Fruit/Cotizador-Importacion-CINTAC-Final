from datetime import date

from django.test import TestCase
from django.core.exceptions import ValidationError

from .models import (
    Login,
    cotizacion_generada,
    ruta_logistica,
    tarifa_contenedor,
    validate_login_password,
)


class LoginViewTests(TestCase):
    def setUp(self):
        self.account = Login.objects.create(
            username='usuario-prueba',
            password='Clave123',
            email='usuario@example.com',
        )

    def test_invalid_credentials_are_rejected(self):
        response = self.client.post(
            '/Cotizador/login/',
            {'username': 'usuario-prueba', 'password': 'Incorrecta1'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Usuario o contraseña incorrectos.')
        self.assertNotIn('login_id', self.client.session)

    def test_valid_credentials_redirect_to_cotizador(self):
        response = self.client.post(
            '/Cotizador/login/',
            {'username': 'usuario-prueba', 'password': 'Clave123'},
        )

        self.assertRedirects(response, '/Cotizador/cotizador/')
        self.assertEqual(self.client.session['login_id'], self.account.pk)

    def test_logout_flushes_session_and_redirects_to_login(self):
        self.client.post(
            '/Cotizador/login/',
            {'username': 'usuario-prueba', 'password': 'Clave123'},
        )

        response = self.client.get('/Cotizador/logout/')

        self.assertRedirects(response, '/Cotizador/login/')
        self.assertNotIn('login_id', self.client.session)

    def test_cotizador_requires_an_authenticated_session(self):
        response = self.client.get('/Cotizador/cotizador/')

        self.assertRedirects(response, '/Cotizador/login/')

    def test_direct_cotizador_access_shows_login_error(self):
        response = self.client.get('/Cotizador/cotizador/', follow=True)

        self.assertContains(
            response,
            'Debes iniciar sesión para acceder al cotizador.',
        )

    def test_password_requires_uppercase_number_and_eight_characters(self):
        for password in ('corta1A', 'solamente8', 'Solamente'):
            with self.subTest(password=password):
                with self.assertRaises(ValidationError):
                    validate_login_password(password)

        validate_login_password('Valida123')


class RutaLogisticaModelTests(TestCase):
    def test_puerto_origen_exposes_only_allowed_countries(self):
        self.assertEqual(
            ruta_logistica._meta.get_field('puerto_origen').choices,
            [
                ('Shanghai, China', 'Shanghai, China'),
                ('Ningbo, China', 'Ningbo, China'),
                ('Shenzhen, China', 'Shenzhen, China'),
                ('Qingdao, China', 'Qingdao, China'),
                ('Guangzhou, China', 'Guangzhou, China'),
                ('Tianjin, China', 'Tianjin, China'),
                ('Yokohama, Japon', 'Yokohama, Japon'),
                ('Tokyo, Japon', 'Tokyo, Japon'),
                ('Nagoya, Japon', 'Nagoya, Japon'),
                ('Kobe, Japon', 'Kobe, Japon'),
                ('Osaka, Japon', 'Osaka, Japon'),
                ('Barcelona, España', 'Barcelona, España'),
                ('Los Angeles, EE.UU', 'Los Angeles, EE.UU'),
                ('Callao, Perú', 'Callao, Perú'),
            ],
        )


class HistorialViewTests(TestCase):
    def setUp(self):
        self.current_user = Login.objects.create(
            username='usuario-actual',
            password='Clave123',
            email='actual@example.com',
        )
        self.other_user = Login.objects.create(
            username='otro-usuario',
            password='Clave123',
            email='otro@example.com',
        )
        self.route = ruta_logistica.objects.create(
            puerto_origen='Shanghai, China',
            puerto_destino='Valparaíso, Chile',
            dias_transito=30,
        )
        self.client.post(
            '/Cotizador/login/',
            {'username': 'usuario-actual', 'password': 'Clave123'},
        )

    def test_historial_muestra_cotizaciones_de_todos_los_usuarios(self):
        own_quote = cotizacion_generada.objects.create(
            id_ruta=self.route,
            id_usuario=self.current_user,
            nombre_cliente='Cliente Actual',
            empresa='Empresa Actual',
            correo_cliente='actual-cliente@example.com',
            descripcion_carga='Carga propia',
            peso_ingresado_kg=100,
            tipo_contenedor='40 HC',
            cantidad_contenedores=1,
            monto_IVA=19,
            monto_total=119,
        )
        other_quote = cotizacion_generada.objects.create(
            id_ruta=self.route,
            id_usuario=self.other_user,
            nombre_cliente='Cliente Otro',
            empresa='Empresa Otro',
            correo_cliente='otro-cliente@example.com',
            descripcion_carga='Carga de otro usuario',
            peso_ingresado_kg=200,
            tipo_contenedor='40 HC',
            cantidad_contenedores=1,
            monto_IVA=38,
            monto_total=238,
        )

        response = self.client.get('/Cotizador/historial/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'#{own_quote.pk}')
        self.assertContains(response, f'#{other_quote.pk}')
        self.assertContains(response, 'usuario-actual')
        self.assertContains(response, 'otro-usuario')
        self.assertContains(response, '2 registros')


class CotizadorViewTests(TestCase):
    def setUp(self):
        account = Login.objects.create(
            username='usuario-cotizador',
            password='Clave123',
            email='cotizador@example.com',
        )
        self.route = ruta_logistica.objects.create(
            puerto_origen='Shanghai, China',
            puerto_destino='Valparaíso, Chile',
            dias_transito=30,
        )
        tarifa_contenedor.objects.create(
            id=201,
            id_ruta=self.route,
            tipo_contenedor='20 HQ',
            peso_max=1000,
            costo_fijo=100,
        )
        tarifa_contenedor.objects.create(
            id=202,
            id_ruta=self.route,
            tipo_contenedor='40 HQ',
            peso_max=2000,
            costo_fijo=150,
        )
        self.client.post(
            '/Cotizador/login/',
            {'username': account.username, 'password': account.password},
        )

    def test_calcular_muestra_una_cotizacion_por_tipo_de_contenedor(self):
        response = self.client.post(
            '/Cotizador/cotizador/',
            {
                'nombre_cliente': 'Cliente Cotizador',
                'empresa': 'Empresa Cotizadora',
                'correo_cliente': 'cliente@example.com',
                'puerto_origen': 'Shanghai, China',
                'puerto_destino': 'Valparaíso, Chile',
                'peso_carga': '1500',
                'descripcion_carga': 'Carga de prueba',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '20 HQ')
        self.assertContains(response, '40 HQ')
        self.assertContains(response, 'Generar informe', count=2)
        self.assertNotContains(response, 'name="tipo_contenedor"')

        report_response = self.client.post(
            '/Cotizador/informe/',
            {'tipo_contenedor': '20 HQ'},
        )

        self.assertEqual(report_response.status_code, 200)
        self.assertEqual(report_response['Content-Type'], 'application/pdf')
        self.assertEqual(
            report_response['Content-Disposition'],
            'attachment; filename="Cotizacion Cliente Cotizador '
            f'{date.today():%d-%m-%Y}.pdf"',
        )
        self.assertTrue(report_response.content.startswith(b'%PDF-1.4'))
        self.assertIn(b'$226.100 CLP', report_response.content)
        self.assertEqual(cotizacion_generada.objects.count(), 1)
        registro = cotizacion_generada.objects.get()
        self.assertEqual(registro.tipo_contenedor, '20 HQ')
        self.assertEqual(registro.peso_ingresado_kg, 1500)
        self.assertIsNone(registro.valor_carga_kg)
        history_response = self.client.get('/Cotizador/historial/')
        self.assertContains(history_response, 'No ingresado')
        self.assertNotIn('cotizaciones_pendientes', self.client.session)

    def test_valor_de_carga_se_guarda_y_aparece_en_el_informe(self):
        response = self.client.post(
            '/Cotizador/cotizador/',
            {
                'nombre_cliente': 'Cliente Con Valor',
                'empresa': 'Empresa Cotizadora',
                'correo_cliente': 'valor@example.com',
                'puerto_origen': 'Shanghai, China',
                'puerto_destino': 'Valparaíso, Chile',
                'peso_carga': '1500',
                'valor_carga': '75000',
                'descripcion_carga': 'Carga valorizada',
            },
        )

        self.assertContains(response, 'Valor de la carga')
        report_response = self.client.post(
            '/Cotizador/informe/',
            {'tipo_contenedor': '20 HQ'},
        )

        self.assertEqual(report_response.status_code, 200)
        self.assertIn(b'Valor de carga: $75.000', report_response.content)
        registro = cotizacion_generada.objects.get()
        self.assertEqual(registro.valor_carga_kg, 75000)
        history_response = self.client.get('/Cotizador/historial/')
        self.assertContains(history_response, '$75.000')


class EditarViewTests(TestCase):
    def setUp(self):
        account = Login.objects.create(
            username='usuario-edicion',
            password='Clave123',
            email='edicion@example.com',
        )
        self.route = ruta_logistica.objects.create(
            puerto_origen='Shanghai, China',
            puerto_destino='Valparaíso, Chile',
            dias_transito=30,
        )
        tarifa_contenedor.objects.create(
            id=301,
            id_ruta=self.route,
            tipo_contenedor='20 HQ',
            peso_max=23000,
            costo_fijo=100,
        )
        tarifa_contenedor.objects.create(
            id=302,
            id_ruta=self.route,
            tipo_contenedor='40 HQ',
            peso_max=25000,
            costo_fijo=150,
        )
        self.client.post(
            '/Cotizador/login/',
            {'username': account.username, 'password': account.password},
        )

    def test_actualizar_ruta_vuelve_a_mostrar_selector(self):
        response = self.client.post(
            f'/Cotizador/editar/{self.route.pk}/',
            {
                'puerto_origen': 'Shanghai, China',
                'puerto_destino': 'Valparaiso, Chile',
                'dias_transito': '31',
                'peso_max_20hq': '23000',
                'costo_fijo_20hq': '110',
                'peso_max_40hq': '25000',
                'costo_fijo_40hq': '160',
            },
        )

        self.assertContains(response, 'Se ha actualizado la ruta')
        self.assertContains(response, 'Ruta que deseas editar')
        self.assertContains(response, 'Cargar ruta')
        self.assertNotContains(response, 'Guardar cambios')
        self.assertNotContains(
            response,
            f'<option value="{self.route.pk}" selected',
        )
