from decimal import Decimal
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from django.conf import settings
from django.utils import timezone
import reportlab
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


FUENTES = Path(reportlab.__file__).parent / 'fonts'
pdfmetrics.registerFont(TTFont('Vera', str(FUENTES / 'Vera.ttf')))
pdfmetrics.registerFont(TTFont('Vera-Bold', str(FUENTES / 'VeraBd.ttf')))


INK = '#182F3A'
MUTED = '#4D6068'
ORANGE = '#BF4D10'


def numero(valor, decimales=0):
    return f'{Decimal(str(valor)):,.{decimales}f}'.translate(str.maketrans(',.', '.,'))


def texto(valor, tam=10, negrita=False, color=INK, derecha=False):
    estilo = ParagraphStyle(
        'cotizacion', fontName='Vera-Bold' if negrita else 'Vera',
        fontSize=tam, leading=tam * 1.35, textColor=colors.HexColor(color),
        alignment=TA_RIGHT if derecha else 0,
    )
    return Paragraph(escape(str(valor)).replace('\n', '<br/>'), estilo)


def tabla(filas, anchos, fondo=None, margen=9):
    reglas = [('VALIGN', (0, 0), (-1, -1), 'TOP')]
    for lado in ('LEFT', 'RIGHT', 'TOP', 'BOTTOM'):
        reglas.append((lado + 'PADDING', (0, 0), (-1, -1), margen))
    if fondo:
        reglas.append(('BACKGROUND', (0, 0), (-1, -1), colors.HexColor(fondo)))
    return Table(filas, colWidths=anchos, style=TableStyle(reglas), hAlign='LEFT')


def generar_cotizacion_pdf(datos, registro, cambio):
    archivo = BytesIO()
    doc = SimpleDocTemplate(archivo, pagesize=A4, leftMargin=36, rightMargin=36,
                            topMargin=88, bottomMargin=64,
                            title=f'Cotización de transporte marítimo N.º {registro.pk}')
    ancho = doc.width - 12  # Margen interno del marco de ReportLab.
    ruta = registro.id_ruta
    cantidad = datos['cantidad_contenedores']
    subtotal = Decimal(str(datos['costo_fijo']))
    total = Decimal(str(datos['monto_total']))
    fecha = timezone.localtime(registro.fecha)
    logo = settings.BASE_DIR / 'ProyectoFinal/static/images/MainCintac/logo.jpg'

    def encabezado(canvas, documento):
        w, h = A4
        canvas.drawImage(str(logo), 42, h - 57, 118, 118 * 35 / 221)
        canvas.setFillColor(colors.HexColor(INK))
        canvas.setFont('Vera-Bold', 10)
        canvas.drawRightString(w - 42, h - 42, f'COTIZACIÓN N.º {registro.pk}')
        canvas.setFont('Vera', 9)
        canvas.drawRightString(w - 42, h - 59, fecha.strftime('Emitida el %d/%m/%Y a las %H:%M'))
        canvas.setStrokeColor(colors.HexColor('#D5DEDF'))
        canvas.line(42, h - 76, w - 42, h - 76)
        canvas.line(42, 48, w - 42, 48)
        canvas.setFillColor(colors.HexColor(MUTED))
        canvas.drawString(42, 32, 'CINTAC  /  Cotizador de transporte marítimo')
        canvas.drawRightString(w - 42, 32, f'Página {documento.page}')

    dias = datos.get('dias_transito')
    secciones = [
        texto(ruta.operacion or 'Transporte marítimo', 10, True, ORANGE),
        texto('Cotización de transporte marítimo', 25, True), Spacer(1, 22),
        tabla([[[texto(etiqueta, 8, True, MUTED), texto(valor, 12, True)]
                for etiqueta, valor in [
                    ('PUERTO DE ORIGEN', ruta.origen_visible),
                    ('PUERTO DE DESTINO', datos['puerto_destino']),
                    ('TRÁNSITO ESTIMADO', f'{dias} días' if dias is not None else 'Sin registro')]]],
              [ancho*.37, ancho*.37, ancho*.26], '#EFF4F4', 12),
        Spacer(1, 28),
    ]
    descripcion = datos['descripcion_carga'] or 'Sin descripción'
    extensa = len(descripcion) > 200 or descripcion.count('\n') > 3
    carga = [texto('Detalle de la carga', 15, True),
             texto('Ver descripción al final' if extensa else descripcion),
             texto(f"Peso total: {numero(datos['peso_ingresado_kg'])} kg")]
    if datos.get('peso_max'):
        carga.append(texto(f"Capacidad por contenedor: {numero(datos['peso_max'])} kg"))
    if datos.get('valor_carga_kg') is not None:
        carga.append(texto(f"Valor de carga: CLP ${numero(datos['valor_carga_kg'])}"))
    cliente = [texto('Cliente', 15, True), texto(datos['nombre_cliente'], negrita=True),
               texto(datos['empresa']), texto(datos['correo_cliente'])]
    secciones.extend([tabla([[cliente, carga]], [ancho*.52, ancho*.48], margen=0), Spacer(1, 30),
                      texto('Desglose del flete', 16, True), Spacer(1, 8)])
    anchos = [ancho*.32, ancho*.16, ancho*.26, ancho*.26]
    def usd(monto):
        return f'USD ${numero(monto, 2)}'
    cabecera = ['Concepto', 'Cantidad', 'Tarifa unitaria', 'Importe']
    valores = [f"Contenedor {datos['tipo_contenedor']}", cantidad,
               usd(subtotal / cantidad) if cantidad else 'Sin registro', usd(subtotal)]
    desglose = [('Flete marítimo', subtotal), ('IVA del flete marítimo (19 %)', datos['monto_IVA'])]
    if registro.flete_local:
        desglose.append(('Flete local', registro.flete_local))
    if registro.gastos_portuarios:
        desglose.append(('Gastos portuarios', registro.gastos_portuarios))
    secciones.extend([
        tabla([[texto(v, 9, True, '#FFFFFF', i > 0) for i, v in enumerate(cabecera)]], anchos, INK),
        tabla([[texto(v, derecha=i > 0) for i, v in enumerate(valores)]], anchos),
        tabla([[texto(etiqueta, derecha=True), texto(usd(valor), derecha=True)] for etiqueta, valor in desglose],
              [ancho*.74, ancho*.26], margen=5), Spacer(1, 12),
    ])
    totales = tabla([[[texto('TOTAL ESTIMADO CON IVA', 9, True, ORANGE), texto(usd(total), 23, True)],
                      [texto('Equivalente en pesos chilenos', 9), texto(f'CLP ${numero(total*cambio)}' if cambio is not None else 'Pendiente', 16, True)]]],
                    [ancho*.59, ancho*.41], '#FFF2E9', 12)
    totales.setStyle(TableStyle([('LINEBEFORE', (0, 0), (0, 0), 3, colors.HexColor('#F26C18'))]))
    secciones.extend([totales, Spacer(1, 28), texto('Base de cálculo', 10, True),
                      texto(f"Conversión referencial: 1 USD = {numero(cambio, 2)} CLP." if cambio is not None
                            else "Conversión a CLP pendiente por falta de un valor publicado."),
                      texto(f"Preparada por: {datos['usuario']}")])
    if datos.get('peso_max'):
        secciones.append(texto(f"Distribución de {numero(datos['peso_ingresado_kg'])} kg en "
                               f"{cantidad} contenedor(es) de {datos['tipo_contenedor']}."))
    if registro.dolar_manual:
        secciones.append(texto(f"Tipo de cambio manual ingresado el {registro.fecha_dolar:%d/%m/%Y}."))
    elif registro.fecha_dolar:
        secciones.append(texto(f"Dólar observado del {registro.fecha_dolar:%d/%m/%Y} · Banco Central de Chile"))
    if datos.get('titulo'):
        secciones.append(texto('Copia del registro histórico', 9, True, MUTED))
    if extensa:
        secciones.extend([Spacer(1, 12), texto('Descripción de la carga', 12, True), texto(descripcion)])
    doc.build(secciones, onFirstPage=encabezado, onLaterPages=encabezado)
    return archivo.getvalue()
