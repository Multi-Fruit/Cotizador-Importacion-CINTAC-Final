"""Expectativas literales calculadas a mano; no invocan el motor de producción."""
import pytest
from playwright.sync_api import expect
from pypdf import PdfReader


pytestmark = pytest.mark.e2e


def fill_quote(page, weight='24000', unit='kg'):
    page.get_by_label('Nombre del cliente').fill('Ana Acero')
    page.get_by_label('Empresa', exact=True).fill('Acero E2E')
    page.get_by_label('Correo del cliente').fill('ana@example.test')
    page.get_by_label('Puerto de origen').select_option('Shanghai, China')
    page.get_by_label('Puerto de destino').select_option('San Antonio, Chile')
    page.get_by_label('Peso de la carga', exact=True).fill(weight)
    page.get_by_label('Unidad del peso').select_option(unit)
    page.get_by_label('Valor de la carga (CLP) (opcional)').fill('500000')
    page.get_by_label('Descripción de la carga').fill('Bobinas de acero')


def calculate(page):
    page.get_by_role('button', name='Calcular cotización').click()


def detail(region, label, value):
    # dl/dt/dd son semánticos; no depende del orden ni de clases de presentación.
    row = region.locator('div').filter(has=region.page.get_by_text(label, exact=True))
    expect(row.locator('dd')).to_have_text(value)


def test_login_and_access(app):
    page, base = app
    page.goto(base + '/Cotizador/cotizador/')
    expect(page.get_by_role('alert')).to_have_text('Debes iniciar sesión para acceder al cotizador.')
    page.get_by_label('Usuario', exact=True).fill('e2e_admin')
    page.get_by_label('Contraseña', exact=True).fill('Incorrecta123')
    page.get_by_role('button', name='Ingresar').click()
    expect(page.get_by_role('alert')).to_have_text('Usuario o contraseña incorrectos.')
    page.get_by_label('Usuario', exact=True).fill('e2e_admin')
    page.get_by_label('Contraseña', exact=True).fill('PruebaE2E123')
    page.get_by_role('button', name='Ingresar').click()
    expect(page.get_by_role('heading', name='Calcula tu transporte')).to_be_visible()
    page.get_by_role('link', name='Cerrar sesión').click()
    page.goto(base + '/Cotizador/cotizador/')
    expect(page.get_by_role('alert')).to_have_text('Debes iniciar sesión para acceder al cotizador.')


@pytest.mark.parametrize('tonnes,kilos,count_20,count_40', [
    ('23', '23000', '1', '1'),
    ('23.001', '23001', '2', '1'),
    ('25', '25000', '2', '1'),
    ('25.001', '25001', '2', '2'),
])
def test_container_recommendations_match_weight_units(
    calculator, tonnes, kilos, count_20, count_40,
):
    page = calculator
    for unit, weight in [('t', tonnes), ('kg', kilos)]:
        fill_quote(page, weight=weight, unit=unit)
        calculate(page)
        expect(page.get_by_label('Unidad del peso')).to_have_value(unit)
        for kind, count in [('20 HQ', count_20), ('40 HQ', count_40)]:
            region = page.get_by_role('region', name=kind, exact=True)
            detail(region, 'Contenedores necesarios', count)


def test_breakdown_and_recalculation(calculator):
    page = calculator
    fill_quote(page)
    calculate(page)
    # 24.000 kg: ceil(24000/23000)=2, ceil(24000/25000)=1.
    for kind, count, freight, vat, total in [
        ('20 HQ', '2', '2002,00', '380,38', '2382,38'),
        ('40 HQ', '1', '1500,00', '285,00', '1785,00'),
    ]:
        region = page.get_by_role('region', name=kind, exact=True)
        detail(region, 'Contenedores necesarios', count)
        detail(region, 'Costo fijo', 'USD ' + freight)
        detail(region, 'IVA (19%)', 'USD ' + vat)
        expect(region.get_by_text('USD ' + total, exact=True)).to_be_visible()
    page.get_by_label('Peso de la carga', exact=True).fill('25001')
    calculate(page)
    region = page.get_by_role('region', name='40 HQ', exact=True)
    detail(region, 'Contenedores necesarios', '2')
    detail(region, 'Costo fijo', 'USD 3000,00')
    detail(region, 'IVA (19%)', 'USD 570,00')
    expect(region.get_by_text('USD 3570,00', exact=True)).to_be_visible()
    expect(region.get_by_text('USD 1785,00', exact=True)).to_have_count(0)


@pytest.mark.parametrize('kind,total,clp,count', [
    ('20 HQ', '2382.38', '$2.263.261', '2'),
    ('40 HQ', '1785.00', '$1.695.750', '1'),
])
def test_download_conversion_and_history(calculator, tmp_path, kind, total, clp, count):
    page = calculator
    fill_quote(page, weight='24,001', unit='t')
    calculate(page)
    with page.expect_download() as pending:
        page.get_by_role('region', name=kind, exact=True).get_by_role(
            'button', name='Generar informe',
        ).click()
    download = pending.value
    assert download.failure() is None
    path = tmp_path / 'cotizacion.pdf'
    download.save_as(path)
    text = '\n'.join(p.extract_text() for p in PdfReader(path).pages)
    # P19 de la planilla: datos de cliente, carga y marca del PDF descargado.
    for expected in ('Ana Acero', 'Acero E2E', 'ana@example.test', 'Bobinas de acero',
                     'Shanghai, China', 'San Antonio, Chile', kind):
        assert expected in text
    pdf = PdfReader(path)
    assert pdf.metadata.author == 'CINTAC'
    assert len(pdf.pages[0].images) > 0
    # 2382.38*950=2263261; 1785*950=1695750. Conversión real del PDF descargado.
    assert f'USD {total}' in text
    assert f'{clp} CLP' in text
    assert '1 USD = $950 CLP' in text
    assert '24,001 t (24.001 kg)' in text
    expect(page.get_by_role('region', name=kind, exact=True)).to_have_count(0)
    page.get_by_role('link', name='Historial', exact=True).click()
    row = page.get_by_role('row').filter(has_text='Ana Acero')
    expect(row).to_have_count(1)
    expect(row.get_by_role('cell', name=f'{count} × {kind}', exact=True)).to_be_visible()
    expect(row).to_contain_text('24,001')
    expect(row).to_contain_text('$500.000')
    expect(row).to_contain_text('e2e_admin')
    # El caso entero permite verificar persistencia sin legitimar truncamiento.
    if kind == '40 HQ':
        expect(row.get_by_role('cell', name='$1785', exact=True)).to_be_visible()
    page.reload()
    expect(page.get_by_role('row').filter(has_text='Ana Acero')).to_have_count(1)


@pytest.mark.parametrize('field,value,validity', [
    ('Nombre del cliente', '', 'valueMissing'),
    ('Empresa', '', 'valueMissing'),
    ('Correo del cliente', '', 'valueMissing'),
    ('Puerto de origen', '', 'valueMissing'),
    ('Puerto de destino', '', 'valueMissing'),
    ('Peso de la carga', '', 'valueMissing'),
    ('Descripción de la carga', '', 'valueMissing'),
    ('Correo del cliente', 'correo-invalido', 'typeMismatch'),
    ('Peso de la carga', '-1', 'patternMismatch'),
    ('Peso de la carga', 'abc', 'patternMismatch'),
    ('Valor de la carga (CLP) (opcional)', '-1', 'rangeUnderflow'),
    ('Valor de la carga (CLP) (opcional)', '1.5', 'stepMismatch'),
])
def test_browser_validation(calculator, field, value, validity):#revisar que onda
    page = calculator
    fill_quote(page)
    control = page.get_by_label(field, exact=True)
    if field.startswith('Puerto'):
        control.select_option(value)
    else:
        control.fill(value)
    calculate(page)
    assert control.evaluate('(element, key) => element.validity[key]', validity)
    expect(page.locator('#quote-results')).to_have_count(0)
    expect(page.get_by_role('alert')).to_have_count(0)


@pytest.mark.parametrize('weight,unit,error', [
    ('0', 'kg', 'Ingresa un peso de carga válido mayor que cero.'),
    ('0.5', 'kg', 'El peso debe equivaler a una cantidad entera de kilogramos.'),
    ('0,0001', 't', 'El peso debe equivaler a una cantidad entera de kilogramos.'),
    ('2147483648', 'kg', 'El peso máximo permitido es'),
])
def test_server_validation_invalidates_previous_quote(calculator, weight, unit, error):
    page = calculator
    fill_quote(page)
    calculate(page)
    expect(page.locator('#quote-results')).to_be_visible()
    page.get_by_label('Peso de la carga', exact=True).fill(weight)
    page.get_by_label('Unidad del peso').select_option(unit)
    calculate(page)
    expect(page.get_by_role('alert')).to_contain_text(error)
    expect(page.locator('#quote-results')).to_have_count(0)
    page.goto(page.url.replace('/cotizador/', '/informe/'))
    expect(page.get_by_role('alert')).to_have_text(
        'Primero debes calcular una cotización antes de generar el informe.',
    )


def test_optional_cargo_value(calculator):
    page = calculator
    fill_quote(page, weight='23000')
    page.get_by_label('Valor de la carga (CLP) (opcional)').fill('')
    calculate(page)
    region = page.get_by_role('region', name='20 HQ', exact=True)
    detail(region, 'Contenedores necesarios', '1')
    expect(region.get_by_text('USD 1191,19', exact=True)).to_be_visible()


@pytest.mark.xfail(strict=True, raises=AssertionError, reason=(
    'Defecto conocido: informe() trunca con int(); el usuario requiere '
    'redondear al entero más cercano con 0,5 hacia arriba.'
))
def test_history_rounds_total_half_up(calculator):
    page = calculator
    # 46.001 kg requieren 3 contenedores 20 HQ: 3003 + 570.57 = 3573.57.
    # Regla confirmada: historial debe mostrar 3574, pero hoy persiste 3573.
    fill_quote(page, weight='46001')
    calculate(page)
    region = page.get_by_role('region', name='20 HQ', exact=True)
    expect(region.get_by_text('USD 3573,57', exact=True)).to_be_visible()
    with page.expect_download():
        region.get_by_role('button', name='Generar informe').click()
    expect(page.locator('#quote-results')).to_have_count(0)
    page.get_by_role('link', name='Historial', exact=True).click()
    row = page.get_by_role('row').filter(has_text='Ana Acero')
    expect(row).to_have_count(1)
    expect(row.get_by_role('cell', name='$3574', exact=True)).to_be_visible()
