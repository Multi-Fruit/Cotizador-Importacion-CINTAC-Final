"""Casos de la planilla Grupo 7; trazabilidad completa en PLANILLA.md.

Los estados históricos APROBADO/RECHAZADO no son expectativas de ejecución.
"""
import re

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from playwright.sync_api import expect

from Cotizador.models import Login, ruta_logistica, tarifa_contenedor
from test_calculator import calculate, fill_quote


pytestmark = pytest.mark.e2e


@pytest.fixture
def admin_account(transactional_db, monkeypatch):
    # P04: ejecutar el comando real, sin interacción ni credenciales reales.
    monkeypatch.setenv('DJANGO_SUPERUSER_PASSWORD', 'AdminE2E123!')
    call_command('createsuperuser', username='staff_e2e',
                 email='staff@example.test', interactive=False, verbosity=0)
    return get_user_model().objects.get(username='staff_e2e')


@pytest.fixture
def admin_page(app, admin_account):
    page, base = app
    page.goto(base + '/admin/')
    page.get_by_label('Nombre de usuario:').fill('staff_e2e')
    page.get_by_label('Contraseña:').fill('AdminE2E123!')
    page.get_by_role('button', name='Iniciar sesión').click()
    expect(page.get_by_role('heading', name='Sitio administrativo')).to_be_visible()
    return page


def test_p01_p06_startup_and_login_form(app):
    page, base = app
    response = page.goto(base + '/')
    assert response.status == 200
    expect(page).to_have_title('Iniciar sesión | CINTAC')
    expect(page.get_by_role('heading', name='Iniciar sesión')).to_be_visible()
    expect(page.get_by_label('Usuario', exact=True)).to_be_editable()
    expect(page.get_by_label('Contraseña', exact=True)).to_have_attribute('type', 'password')
    expect(page.get_by_role('button', name='Ingresar')).to_be_visible()


def test_p02_p03_home_link_to_login(app):
    page, base = app
    page.goto(base + '/')
    # Requisito literal: no reemplazar el enlace ausente por page.goto(login).
    page.get_by_role('link', name='Cotizador', exact=True).click(timeout=5000)
    expect(page).to_have_url(base + '/Cotizador/login/')
    expect(page.get_by_label('Usuario', exact=True)).to_be_visible()


def test_p04_superuser_access(admin_page, admin_account):
    assert admin_account.is_staff and admin_account.is_superuser
    expect(admin_page.get_by_role('link', name='Logins', exact=True)).to_be_visible()
    expect(admin_page.get_by_role('link', name='Usuarios', exact=True)).to_be_visible()


def open_login_form(page):
    page.get_by_role('link', name='Logins', exact=True).click()
    page.get_by_role('link', name='Añadir login', exact=True).click()
    page.get_by_label('Username:', exact=True).fill('nuevo_e2e')
    page.get_by_label('Password:', exact=True).fill('Segura123')
    page.get_by_label('Email:', exact=True).fill('nuevo@example.test')


def test_p05_p07_p08_p09_create_user_and_login(admin_page):
    page = admin_page
    open_login_form(page)
    page.get_by_role('button', name='Guardar', exact=True).click()
    expect(page.get_by_role('link', name='nuevo_e2e', exact=True)).to_be_visible()
    account = Login.objects.get(username='nuevo_e2e')
    assert account.rol == 'Administrador CINTAC'
    expect(page.get_by_role('row').filter(has_text='nuevo_e2e')).to_contain_text(account.rol)
    # La sesión auth del admin no sustituye la sesión Login del cotizador.
    page.goto(page.url.split('/admin/')[0] + '/Cotizador/login/')
    page.get_by_label('Usuario', exact=True).fill('nuevo_e2e')
    page.get_by_label('Contraseña', exact=True).fill('Segura123')
    page.get_by_role('button', name='Ingresar').click()
    expect(page).to_have_url(re.compile(r'/Cotizador/cotizador/$'))
    expect(page.get_by_role('heading', name='Calcula tu transporte')).to_be_visible()
    page.reload()
    expect(page.get_by_role('button', name='Calcular cotización')).to_be_visible()


@pytest.mark.parametrize('field,value,message', [
    pytest.param('Password:', 'Abc123', 'La contraseña debe tener al menos 8 caracteres.', id='P09-fila16-P10-longitud'),
    pytest.param('Password:', 'segura123', 'La contraseña debe contener al menos una mayúscula.', id='P09-fila16-P10-mayuscula'),
    pytest.param('Password:', 'Seguraabc', 'La contraseña debe contener al menos un número.', id='P09-fila16-P10-numero'),
    pytest.param('Username:', 'abcd', 'El nombre de usuario debe tener al menos 5 caracteres.', id='P11-longitud'),
    pytest.param('Username:', 'nombre usuario', 'El nombre de usuario solo puede contener letras, números y guiones bajos.', id='P11-espacios'),
    pytest.param('Username:', 'nombre@usuario', 'El nombre de usuario solo puede contener letras, números y guiones bajos.', id='P11-simbolos'),
    pytest.param('Email:', 'sinarroba.test', 'El correo electrónico no tiene un formato válido.', id='P12-arroba'),
    pytest.param('Email:', 'ana@dominio', 'El correo electrónico no tiene un formato válido.', id='P12-dominio'),
])
def test_admin_user_validation(admin_page, field, value, message):
    page = admin_page
    open_login_form(page)
    page.get_by_label(field, exact=True).fill(value)
    count = Login.objects.count()
    page.get_by_role('button', name='Guardar', exact=True).click()
    expect(page.get_by_text(message, exact=True)).to_be_visible()
    assert Login.objects.count() == count
    expect(page.get_by_label(field, exact=True)).to_be_visible()


def test_p13_p14_direct_access_is_denied(app):
    page, base = app
    page.goto(base + '/Cotizador/cotizador/')
    expect(page).to_have_url(base + '/Cotizador/login/')
    expect(page.get_by_role('alert')).to_have_text('Debes iniciar sesión para acceder al cotizador.')
    expect(page.get_by_role('button', name='Calcular cotización')).to_have_count(0)


def test_p15_create_route_in_admin(admin_page):
    page = admin_page
    page.get_by_role('link', name='Ruta_logisticas', exact=True).click()
    page.get_by_role('link', name='Añadir ruta_logistica', exact=True).click()
    page.get_by_label('Puerto origen:', exact=True).select_option('Ningbo, China')
    page.get_by_label('Puerto destino:', exact=True).select_option('Valparaíso, Chile')
    page.get_by_label('Dias transito:', exact=True).fill('31')
    page.get_by_role('button', name='Guardar', exact=True).click()
    expect(page.get_by_role('link', name='Ningbo, China', exact=True)).to_be_visible()
    route = ruta_logistica.objects.get(puerto_origen='Ningbo, China')
    assert (route.puerto_destino, route.dias_transito) == ('Valparaíso, Chile', 31)
    page.reload()
    expect(page.get_by_role('link', name='Ningbo, China', exact=True)).to_be_visible()


def test_p16_create_tariff_in_admin(admin_page):
    page = admin_page
    route = ruta_logistica.objects.get(puerto_origen='Shanghai, China')
    page.get_by_role('link', name='Tarifa_contenedors', exact=True).click()
    page.get_by_role('link', name='Añadir tarifa_contenedor', exact=True).click()
    page.get_by_label('Id ruta:', exact=True).select_option(str(route.pk))
    page.get_by_label('Tipo contenedor:', exact=True).fill('20 TEST')
    page.get_by_label('Peso max:', exact=True).fill('20000')
    page.get_by_label('Costo fijo:', exact=True).fill('1100')
    page.get_by_label('Moneda original:', exact=True).fill('USD')
    page.get_by_role('button', name='Guardar', exact=True).click()
    expect(page.get_by_role('row').filter(has_text='20 TEST')).to_contain_text('1100')
    tariff = tarifa_contenedor.objects.get(tipo_contenedor='20 TEST')
    assert (tariff.id_ruta_id, tariff.peso_max, tariff.costo_fijo, tariff.moneda_original) == (route.pk, 20000, 1100, 'USD')
    page.reload()
    expect(page.get_by_role('row').filter(has_text='20 TEST')).to_have_count(1)


def test_p17_select_only_40hq_above_20_tonnes(calculator):
    fill_quote(calculator, weight='20001')
    calculate(calculator)
    expect(calculator.get_by_role('region', name='40 HQ', exact=True)).to_be_visible()
    expect(calculator.get_by_role('region', name='20 HQ', exact=True)).to_have_count(0)


@pytest.mark.parametrize('weight', ['-1500', 'abc'], ids=['P18-negativo', 'P18-letras'])
def test_p18_invalid_weight_browser_and_server(calculator, weight):
    page = calculator
    fill_quote(page, weight=weight)
    calculate(page)
    field = page.get_by_label('Peso de la carga', exact=True)
    assert field.evaluate('(e) => e.validity.patternMismatch && !e.validity.valid')
    assert field.evaluate('(e) => e.validationMessage.length > 0')
    expect(page.locator('#quote-results')).to_have_count(0)
    # Además comprobar Django si se elude la restricción HTML, con POST del navegador.
    field.evaluate('(e) => e.form.noValidate = true')
    calculate(page)
    expect(page.get_by_role('alert')).to_have_text('Ingresa un peso de carga válido mayor que cero.')
    expect(page.locator('#quote-results')).to_have_count(0)
