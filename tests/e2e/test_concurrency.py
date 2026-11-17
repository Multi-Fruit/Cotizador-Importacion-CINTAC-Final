"""P20: tres navegadores aislados, POST simultáneos y presupuesto de 2 s."""
import threading
from urllib.parse import urlsplit

import pytest
from django.conf import settings
from django.contrib.sessions.models import Session
from playwright.sync_api import expect

from Cotizador.models import Login
from Cotizador.urls import urlpatterns
from test_calculator import fill_quote


pytestmark = pytest.mark.e2e


@pytest.mark.parametrize('environment', ['local', 'neon'], ids=['P20-local', 'P20-Neon'])
@pytest.mark.django_db(transaction=True)
def test_p20_three_concurrent_sessions(environment, request, monkeypatch):
    if environment == 'neon' and not getattr(settings, 'E2E_NEON', False):
        pytest.skip('P20 exige Neon exclusivo de pruebas; usar settings_test_neon y credenciales E2E_NEON_*')
    if environment == 'local' and getattr(settings, 'E2E_NEON', False):
        pytest.skip('Variante local: ejecutar con settings_test')
    page, base = request.getfixturevalue('app')
    new_context = request.getfixturevalue('new_context')
    barrier = threading.Barrier(3, timeout=10)
    pattern = next(p for p in urlpatterns if p.name == 'cotizador')
    original = pattern.callback

    def simultaneous_view(http_request, *args, **kwargs):
        if http_request.method == 'POST':
            # Impide que tres consultas secuenciales aparenten concurrencia.
            barrier.wait()
        return original(http_request, *args, **kwargs)

    monkeypatch.setattr(pattern, 'callback', simultaneous_view)
    pages = []
    external = []

    def local_only(route):
        parsed = urlsplit(route.request.url)
        if parsed.netloc == urlsplit(base).netloc:
            route.continue_()
        elif parsed.hostname == 'fonts.googleapis.com':
            route.fulfill(status=200, content_type='text/css', body='')
        else:
            external.append(route.request.url)
            route.abort()

    for index in range(3):
        username = f'concurrent_{index}'
        Login.objects.create(username=username, password='Concurrent123', email=f'c{index}@example.test')
        context = new_context()
        context.route('**/*', local_only)
        current = context.new_page()
        pages.append(current)
        current.goto(base + '/Cotizador/login/')
        current.get_by_label('Usuario', exact=True).fill(username)
        current.get_by_label('Contraseña', exact=True).fill('Concurrent123')
        current.get_by_role('button', name='Ingresar').click()
        expect(current.get_by_role('heading', name='Calcula tu transporte')).to_be_visible()
        fill_quote(current, weight=['23000', '24000', '25001'][index])
        current.get_by_label('Nombre del cliente').fill(['Ana Acero', 'Beto Acero', 'Carla Acero'][index])

    # Iniciar sin esperar la respuesta: las 3 llegan a la barrera del servidor.
    for current in pages:
        current.evaluate("""() => {
            const form = document.querySelector('form');
            const start = performance.now();
            window.concurrentResult = fetch(form.action, {
                method: 'POST', body: new FormData(form), credentials: 'same-origin'
            }).then(async response => ({status: response.status,
                html: await response.text(), elapsed: performance.now() - start}));
        }""")

    timings = []
    session_ids = set()
    for index, current in enumerate(pages):
        result = current.evaluate('() => window.concurrentResult')
        assert result['status'] == 200
        timings.append(result['elapsed'])
        current.set_content(result['html'])
        region = current.get_by_role('region', name='40 HQ', exact=True)
        expect(region.get_by_text(['Ana Acero', 'Beto Acero', 'Carla Acero'][index], exact=True)).to_be_visible()
        expect(region.get_by_text(['USD 1785,00', 'USD 1785,00', 'USD 3570,00'][index], exact=True)).to_be_visible()
        # Verifica que cada transacción de sesión conservó su cálculo pendiente.
        current.goto(base + '/Cotizador/informe/')
        expect(current.get_by_role('alert')).to_have_count(0)
        expect(current.get_by_role('heading', name='Cotización lista')).to_be_visible()
        session_id = next(c['value'] for c in current.context.cookies() if c['name'] == settings.SESSION_COOKIE_NAME)
        session_ids.add(session_id)
        pending = Session.objects.get(session_key=session_id).get_decoded()['cotizaciones_pendientes']
        assert len(pending) == 2
        assert {q['nombre_cliente'] for q in pending} == {['Ana Acero', 'Beto Acero', 'Carla Acero'][index]}
        quote_40 = next(q for q in pending if q['tipo_contenedor'] == '40 HQ')
        assert quote_40['monto_total'] == ['1785.00', '1785.00', '3570.00'][index]
    assert len(session_ids) == 3
    assert not external, external
    request.node.user_properties.append(('response_times_ms', ','.join(f'{ms:.2f}' for ms in timings)))
    assert max(timings) < 2000, f'P20 exige menos de 2000 ms por petición: {timings}'
