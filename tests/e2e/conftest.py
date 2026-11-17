from decimal import Decimal
from urllib.parse import urlsplit
import socket

import pytest
from playwright.sync_api import expect

from Cotizador.models import Login, ruta_logistica, tarifa_contenedor


@pytest.fixture(scope='session', autouse=True)
def sync_playwright_with_django():
    # Playwright sync mantiene un event loop en el hilo de pytest. El ORM de
    # fixtures se usa secuencialmente y live_server tiene su propio hilo.
    # Esta excepción sólo existe durante E2E, nunca en settings de producción.
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv('DJANGO_ALLOW_ASYNC_UNSAFE', 'true')
        yield


@pytest.fixture(autouse=True)
def isolated_services(monkeypatch):
    """Servidor y navegador sólo pueden acceder al equipo local."""
    from Cotizador import views

    monkeypatch.setattr(views, 'USD_TO_CLP', Decimal('950'))
    original_connect = socket.socket.connect

    def local_connect(sock, address):
        if isinstance(address, tuple) and address[0] not in {
            'localhost', '127.0.0.1', '::1',
        }:
            raise AssertionError(f'Conexión externa no permitida en E2E: {address}')
        return original_connect(sock, address)

    monkeypatch.setattr(socket.socket, 'connect', local_connect)


@pytest.fixture
def browser_context_args(browser_context_args):
    return {**browser_context_args, 'locale': 'es-CL', 'service_workers': 'block'}


@pytest.fixture
def catalog(transactional_db):
    """Datos confirmados, visibles al hilo live_server; se limpian en cada prueba."""
    account = Login.objects.create(
        username='e2e_admin', password='PruebaE2E123', email='admin@example.test',
    )
    route = ruta_logistica.objects.create(
        puerto_origen='Shanghai, China', puerto_destino='San Antonio, Chile',
        dias_transito=30,
    )
    for kind, capacity, cost in [('20 HQ', 23000, 1001), ('40 HQ', 25000, 1500)]:
        tarifa_contenedor.objects.create(
            id_ruta=route, tipo_contenedor=kind, peso_max=capacity,
            costo_fijo=cost, moneda_original='USD',
        )
    return account


@pytest.fixture
def app(page, live_server, catalog):
    external = []
    origin = urlsplit(live_server.url).netloc

    def route_request(route):
        if urlsplit(route.request.url).netloc == origin:
            route.continue_()
        elif urlsplit(route.request.url).hostname == 'fonts.googleapis.com':
            route.fulfill(status=200, content_type='text/css', body='/* offline E2E */')
        else:
            external.append(route.request.url)
            route.abort()

    page.context.route('**/*', route_request)
    yield page, live_server.url
    assert not external, f'El navegador intentó acceder a servicios externos: {external}'


@pytest.fixture
def calculator(app):
    page, base_url = app
    page.goto(base_url + '/Cotizador/login/')
    page.get_by_label('Usuario', exact=True).fill('e2e_admin')
    page.get_by_label('Contraseña', exact=True).fill('PruebaE2E123')
    page.get_by_role('button', name='Ingresar').click()
    expect(page.get_by_role('heading', name='Calcula tu transporte')).to_be_visible()
    return page
