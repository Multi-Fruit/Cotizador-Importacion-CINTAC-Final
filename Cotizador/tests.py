from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch
from io import BytesIO

from pypdf import PdfReader

from django.test import TestCase
from django.core.exceptions import ValidationError

from .models import (
    DolarObservado,
    Login,
    cotizacion_generada,
    ruta_logistica,
    tarifa_contenedor,
    validate_login_password,
)


def texto_pdf(respuesta):
    return '\n'.join(pagina.extract_text() for pagina in PdfReader(BytesIO(respuesta.content)).pages)


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
                ('San antonio, Chile', 'San antonio, Chile'),
                ('Valparaíso, Chile', 'Valparaíso, Chile'),
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


    def test_filtros_combinados_y_fechas_inclusivas(self):
        from django.utils import timezone

        registro = cotizacion_generada.objects.create(
            id_ruta=self.route, id_usuario=self.current_user, nombre_cliente='Ana Pérez',
            empresa='Aceros del Sur', correo_cliente='ana@example.com', descripcion_carga='Acero',
            peso_ingresado_kg=1000, tipo_contenedor='20 HQ', cantidad_contenedores=1,
            monto_IVA=19, monto_total=119,
        )
        dia = timezone.localdate(registro.fecha).isoformat()
        filtros = dict(id=registro.pk, cliente='CEROS', ruta=self.route.pk,
                       operacion='Importación', desde=dia, hasta=dia)
        url = '/Cotizador/historial/'
        self.assertContains(self.client.get(url, filtros), f'#{registro.pk}')
        for cambio in [dict(id=registro.pk+1), dict(cliente='otro'), dict(operacion='Exportación'),
                       dict(desde='2000-01-01', hasta='2000-01-02')]:
            self.assertContains(self.client.get(url, filtros | cambio), 'No se encontraron')
        self.assertContains(self.client.get(url, {'desde': '2026-02-02', 'hasta': '2026-02-01'}),
                            'La fecha final debe ser igual o posterior')


class CotizadorViewTests(TestCase):
    def setUp(self):
        from django.utils import timezone
        DolarObservado.objects.create(fecha=timezone.localdate(), valor=950)
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

    def test_costos_por_embarque_en_ambas_operaciones(self):
        datos = dict(nombre_cliente='Cliente Prueba', empresa='Empresa Prueba',
                     correo_cliente='cliente@example.com', peso_carga='1500',
                     descripcion_carga='Acero', flete_local='25.55', gastos_portuarios='40.15')
        for origen, destino, operacion in [
            ('Shanghai, China', 'Valparaíso, Chile', 'Importación'),
            ('Valparaíso, Chile', 'Callao, Perú', 'Exportación'),
        ]:
            self.route.puerto_origen, self.route.puerto_destino = origen, destino
            self.route.save()
            datos.update(puerto_origen=origen, puerto_destino=destino, operacion=operacion)
            respuesta = self.client.post('/Cotizador/cotizador/', datos)
            resultado = respuesta.context['resultados'][0]
            self.assertEqual(resultado['cantidad_contenedores'], 2)
            self.assertEqual(resultado['monto_total'], Decimal('303.70'))
            pdf = self.client.post('/Cotizador/informe/', {'tipo_contenedor': '20 HQ'})
            contenido = texto_pdf(pdf)
            for valor in ('Flete local', 'Gastos portuarios', 'USD $303,70'):
                self.assertIn(valor, contenido)
            self.assertEqual(cotizacion_generada.objects.latest('pk').monto_total, Decimal('303.70'))
        invalida = self.client.post('/Cotizador/cotizador/', datos | {'flete_local': '-1'})
        self.assertIn('flete_local', invalida.context['adicionales'].errors)

    def test_pdf_conserva_tasa_del_calculo(self):
        DolarObservado.objects.update(valor=Decimal('1044.08'))
        datos = dict(nombre_cliente='Cliente Prueba', empresa='Empresa Prueba',
                     correo_cliente='cliente@example.com', peso_carga='1000',
                     descripcion_carga='Acero', puerto_origen=self.route.puerto_origen,
                     puerto_destino=self.route.puerto_destino, operacion='Importación')
        respuesta = self.client.post('/Cotizador/cotizador/', datos)
        self.assertContains(respuesta, '1.044,08')
        DolarObservado.objects.update(valor=1050)
        pdf = self.client.post('/Cotizador/informe/', {'tipo_contenedor': '20 HQ'})
        self.assertIn('1.044,08 CLP', texto_pdf(pdf))
        self.assertIn('CLP $124.246', texto_pdf(pdf))
        self.assertEqual(cotizacion_generada.objects.get().tasa_usd_clp, Decimal('1044.08'))

    @patch('Cotizador.views.obtener_dolar', return_value=None)
    def test_tasa_manual_de_emergencia(self, consulta):
        datos = dict(nombre_cliente='Cliente Prueba', empresa='Empresa Prueba',
                     correo_cliente='cliente@example.com', peso_carga='1000',
                     descripcion_carga='Acero', puerto_origen=self.route.puerto_origen,
                     puerto_destino=self.route.puerto_destino, operacion='Importación')
        url = '/Cotizador/cotizador/'
        for invalida in ('0', '-5', 'NaN', '1,2345'):
            self.assertContains(self.client.post(url, datos | {'tasa_manual': invalida}),
                                'Ingresa una tasa positiva')
        respuesta = self.client.post(url, datos | {'tasa_manual': '1.050,50'})
        self.assertContains(respuesta, 'Tipo de cambio manual')
        self.assertContains(respuesta, '$125.010 CLP')
        pdf = texto_pdf(self.client.post('/Cotizador/informe/', {'tipo_contenedor': '20 HQ'}))
        self.assertIn('Tipo de cambio manual', pdf)
        self.assertNotIn('Banco Central de Chile', pdf)
        registro = cotizacion_generada.objects.get()
        self.assertTrue(registro.dolar_manual)
        self.assertEqual(registro.tasa_usd_clp, Decimal('1050.50'))
        self.assertEqual(DolarObservado.objects.get().valor, 950)
        self.client.post(url, datos)
        self.assertIsNone(self.client.session['cotizaciones_pendientes'][0]['tasa_usd_clp'])

    @patch('Cotizador.dolar.consultar_banco', side_effect=TimeoutError)
    @patch.dict('os.environ', {'BCCH_API_TOKEN': 'prueba'})
    def test_indicador_sin_conexion(self, consulta):
        from django.core.cache import cache
        from django.utils import timezone
        cache.clear()
        DolarObservado.objects.all().delete()
        respuesta = self.client.get('/Cotizador/cotizador/')
        self.assertContains(respuesta, 'Conversión a CLP pendiente')
        consulta.assert_called_once()
        DolarObservado.objects.create(fecha=timezone.localdate() - timedelta(days=1), valor=900)
        self.assertContains(self.client.get('/Cotizador/cotizador/'), 'Último dato disponible')
        cache.clear()

    def test_crear_ruta_segun_operacion(self):
        datos = {
            'puerto_origen': 'San Antonio, Chile', 'puerto_destino': 'Callao, Perú',
            'operacion': 'Importación', 'dias_transito': 5,
            'peso_max_20hq': 23000, 'peso_max_40hq': 25000,
            'costo_fijo_20hq': 100, 'costo_fijo_40hq': 150,
        }
        crear = '/Cotizador/crear/'
        self.assertContains(self.client.post(crear, datos), 'Selecciona puertos válidos')
        datos['operacion'] = 'Exportación'
        ruta = self.client.post(crear, datos).context['created_route']
        self.assertEqual(ruta.operacion, 'Exportación')
        self.assertEqual(tarifa_contenedor.objects.filter(id_ruta=ruta).count(), 2)
        self.assertContains(self.client.post(crear, datos), 'ya existe')
        datos['puerto_destino'] = 'Guayaquil, Ecuador'
        nueva = self.client.post(crear, datos).context['created_route']
        nueva.full_clean()
        self.assertEqual(nueva.operacion, 'Exportación')
        self.assertIn({'operacion': 'Exportación', 'origen': 'San Antonio, Chile',
                       'destino': 'Guayaquil, Ecuador'},
                      self.client.get('/Cotizador/cotizador/').context['rutas_disponibles'])
        datos.update(operacion='Importación', puerto_origen='Callao, Perú',
                     puerto_destino='San Antonio, Chile')
        self.assertEqual(self.client.post(crear, datos).context['created_route'].operacion, 'Importación')

    def test_logo_regresa_al_cotizador_con_la_sesion_activa(self):
        inicio = '/Cotizador/cotizador/'
        usuario = self.client.session['login_id']
        for pagina in ('cotizador', 'historial', 'informe', 'crear', 'editar', 'eliminar'):
            with self.subTest(pagina=pagina):
                pantalla = self.client.get(f'/Cotizador/{pagina}/')
                self.assertContains(pantalla, 'Usuario: <strong>usuario-cotizador</strong>')
                self.assertContains(pantalla, f'class="brand" href="{inicio}"')
                self.assertContains(pantalla, 'class="dark-button quote-logout" href="/Cotizador/logout/"')
                self.assertEqual(self.client.get(inicio).status_code, 200)
                self.assertEqual(self.client.session['login_id'], usuario)
        self.client.get('/Cotizador/logout/')
        self.assertNotIn('login_id', self.client.session)
        self.assertRedirects(self.client.get(inicio), '/Cotizador/login/')

    def test_calcular_muestra_una_cotizacion_por_tipo_de_contenedor(self):
        response = self.client.post(
            '/Cotizador/cotizador/',
            {
                'nombre_cliente': 'Cliente Cotizador',
                'empresa': 'Empresa Cotizadora',
                'correo_cliente': 'cliente@example.com',
                'puerto_origen': 'Shanghai, China',
                'puerto_destino': 'Valparaíso, Chile',
                'operacion': 'Importación',
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
        self.assertTrue(report_response.content.startswith(b'%PDF-'))
        self.assertIn('CLP $226.100', texto_pdf(report_response))
        self.assertEqual(cotizacion_generada.objects.count(), 1)
        registro = cotizacion_generada.objects.get()
        self.assertEqual(registro.tipo_contenedor, '20 HQ')
        self.assertEqual(registro.peso_ingresado_kg, 1500)
        self.assertIsNone(registro.valor_carga_kg)
        history_response = self.client.get('/Cotizador/historial/')
        self.assertContains(history_response, 'No ingresado')
        detalle = f'/Cotizador/historial/{registro.pk}/detalle/'
        self.assertContains(history_response, detalle)
        vista = self.client.get(detalle)
        self.assertEqual(vista.content, report_response.content)
        self.assertTrue(vista['Content-Disposition'].startswith('inline'))
        descarga = self.client.get(detalle + '?descargar=1')
        self.assertEqual(descarga.content, vista.content)
        self.assertTrue(descarga['Content-Disposition'].startswith('attachment'))
        cotizacion_generada.objects.filter(pk=registro.pk).update(comprobante_pdf=None)
        copia = self.client.get(detalle)
        self.assertIn('Copia del registro histórico', texto_pdf(copia))
        self.assertIn('USD $238,00', texto_pdf(copia))
        self.assertEqual(self.client.get('/Cotizador/historial/999999/detalle/').status_code, 404)
        self.client.get('/Cotizador/logout/')
        self.assertRedirects(self.client.get(detalle), '/Cotizador/login/')
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
                'operacion': 'Importación',
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
        self.assertIn('Valor de carga: CLP $75.000', texto_pdf(report_response))
        registro = cotizacion_generada.objects.get()
        self.assertEqual(registro.valor_carga_kg, 75000)
        history_response = self.client.get('/Cotizador/historial/')
        self.assertContains(history_response, '$75.000')

    def test_operacion_depende_del_sentido_de_la_ruta(self):
        for origen, destino, operacion, otra in [
            ('San antonio, Chile', 'Callao, Perú', 'Exportación', 'Importación'),
            ('Valparaíso, Chile', 'Callao, Perú', 'Exportación', 'Importación'),
            ('Callao, Perú', 'San Antonio, Chile', 'Importación', 'Exportación'),
        ]:
            with self.subTest(origen=origen, destino=destino):
                self.route.puerto_origen = origen
                self.route.puerto_destino = destino
                self.route.save()
                datos = {
                    'nombre_cliente': 'Cliente Prueba', 'empresa': 'Empresa Prueba',
                    'correo_cliente': 'cliente@example.com', 'peso_carga': '1000',
                    'descripcion_carga': 'Carga de prueba',
                    'puerto_origen': self.route.origen_visible, 'puerto_destino': destino,
                    'operacion': otra,
                }
                respuesta = self.client.post('/Cotizador/cotizador/', datos)
                self.assertContains(respuesta, 'Selecciona una ruta válida')
                self.assertNotIn('cotizaciones_pendientes', self.client.session)
                datos['operacion'] = operacion
                respuesta = self.client.post('/Cotizador/cotizador/', datos)
                self.assertContains(respuesta, 'Generar informe', count=2)
                pdf = self.client.post('/Cotizador/informe/', {'tipo_contenedor': '20 HQ'})
                self.assertIn(operacion, texto_pdf(pdf))
                self.assertContains(self.client.get('/Cotizador/historial/'), operacion)

    def test_convierte_toneladas_a_kilogramos(self):
        response = self.client.post(
            '/Cotizador/cotizador/',
            {
                'nombre_cliente': 'Cliente Toneladas',
                'empresa': 'Empresa Cotizadora',
                'correo_cliente': 'toneladas@example.com',
                'puerto_origen': 'Shanghai, China',
                'puerto_destino': 'Valparaíso, Chile',
                'operacion': 'Importación',
                'peso_carga': '1.5',
                'unidad_peso': 'ton',
                'descripcion_carga': 'Carga pesada',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '1500 kg')
        self.assertEqual(
            response.context['resultados'][0]['peso_carga'],
            1500,
        )


class EliminarRutaViewTests(TestCase):
    def setUp(self):
        account = Login.objects.create(
            username='usuario-eliminar',
            password='Clave123',
            email='eliminar@example.com',
        )
        self.route = ruta_logistica.objects.create(
            puerto_origen='Shanghai, China',
            puerto_destino='Valparaíso, Chile',
            dias_transito=30,
        )
        self.client.post(
            '/Cotizador/login/',
            {'username': account.username, 'password': account.password},
        )

    def test_muestra_las_rutas_en_un_desplegable(self):
        response = self.client.get('/Cotizador/eliminar/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="ruta_id"')
        self.assertContains(response, 'Shanghai, China')
        self.assertContains(response, 'Valparaíso, Chile')

    def test_elimina_la_ruta_seleccionada(self):
        remaining_route = ruta_logistica.objects.create(
            puerto_origen='Ningbo, China',
            puerto_destino='San Antonio, Chile',
            dias_transito=32,
        )
        response = self.client.post(
            '/Cotizador/eliminar/',
            {'ruta_id': self.route.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'La ruta fue eliminada correctamente.')
        self.assertContains(response, 'Ruta eliminada: Shanghai, China')
        self.assertContains(response, 'Ningbo, China')
        self.assertContains(response, str(remaining_route.puerto_destino))
        self.assertFalse(
            ruta_logistica.objects.filter(pk=self.route.pk).exists()
        )


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
