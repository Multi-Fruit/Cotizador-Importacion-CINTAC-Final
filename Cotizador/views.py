from decimal import Decimal
from math import ceil
import re

from django.core.exceptions import ValidationError
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render

from .forms import CrearRutaForm
from .models import (
    Login,
    cotizacion_generada,
    ruta_logistica,
    tarifa_contenedor,
    validate_login_email,
    valida_empresa,
    valida_nombre,
)

USD_TO_CLP = Decimal('950')

ORIGENES_CON_DESTINO_CALLAO = {
    'San antonio, Chile',
    'Valparaíso, Chile',
}

DESTINO_CALLAO = 'Callao, Perú'


def _pdf_escape(value):
    return str(value).replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')


def _safe_filename(value):
    return re.sub(r'[<>:"/\\|?*]+', '', str(value)).strip()


def _format_clp(value):
    if value is None:
        return 'No ingresado'
    return f'${value:,.0f}'.replace(',', '.')

def _build_quote_pdf(data, registro):
    total_clp = (
        Decimal(str(data['monto_total'])) * USD_TO_CLP
    ).quantize(Decimal('1'))
    def text(value):
        return _pdf_escape(value).encode('latin-1', errors='replace').decode('latin-1')

    def line(value, x, y, font='F1', size=10, color='0.15 0.20 0.23'):
        return (
            f'{color} rg BT /{font} {size} Tf {x} {y} Td '
            f'({text(value)}) Tj ET'
        )

    def box(x, y, width, height, color, stroke=False):
        operator = 'B' if stroke else 'f'
        return f'{color} rg {x} {y} {width} {height} re {operator}'

    stream_lines = [
        box(0, 700, 612, 92, '0.11 0.19 0.23'),
        box(0, 700, 612, 6, '0.95 0.44 0.13'),
        line('CINTAC', 42, 752, 'F2', 28, '1 1 1'),
        line('COTIZACION DE TRANSPORTE', 42, 728, 'F1', 11, '1 1 1'),
        line(f'ID #{registro.pk}', 470, 758, 'F2', 11, '1 1 1'),
        line(f'{registro.fecha:%d/%m/%Y %H:%M}', 424, 738, 'F1', 9, '0.84 0.88 0.88'),
        line('DATOS DEL CLIENTE', 42, 675, 'F2', 11, '0.95 0.44 0.13'),
        box(42, 555, 528, 102, '0.97 0.98 0.98'),
        box(42, 653, 528, 4, '0.95 0.44 0.13'),
        line(f'Cliente: {data["nombre_cliente"]}', 58, 630),
        line(f'Empresa: {data["empresa"]}', 58, 610),
        line(f'Correo: {data["correo_cliente"]}', 58, 590),
        line(f'Usuario: {data["usuario"]}', 330, 630),
        line(f'Contenedor: {data["tipo_contenedor"]}', 330, 610),
        line(f'Peso: {data["peso_ingresado_kg"]} kg', 330, 590),
        line('DETALLE DE LA COTIZACION', 42, 530, 'F2', 11, '0.95 0.44 0.13'),
        box(42, 385, 528, 127, '1 1 1', True),
        line(
            f'Ruta: {data["puerto_origen"]} -> {data["puerto_destino"]}',
            58, 488, 'F2', 10, '0.11 0.25 0.35'
        ),
        line(
            f'Descripcion: {data["descripcion_carga"] or "Sin descripcion"}',
            58, 468, 'F1', 9
        ),
        line(
            f'Valor de carga: {_format_clp(data["valor_carga_kg"])}',
            58, 448, 'F1', 9
        ),
        line(
            f'Contenedores necesarios: {data["cantidad_contenedores"]}',
            58, 425, 'F1', 10
        ),
        line(
            f'Costo fijo: USD {Decimal(str(data["costo_fijo"])):.2f}',
            330, 425, 'F1', 10
        ),
        line(
            f'IVA (19%): USD {Decimal(str(data["monto_IVA"])):.2f}',
            330, 405, 'F1', 10
        ),
        box(42, 285, 528, 88, '0.11 0.19 0.23'),
        line('TOTAL ESTIMADO', 62, 345, 'F2', 11, '1 1 1'),
        line(
            f'USD {Decimal(str(data["monto_total"])):.2f}',
            62, 315, 'F2', 24, '1 1 1'
        ),
        line('CONVERSION A PESOS CHILENOS', 330, 345, 'F2', 9, '0.95 0.44 0.13'),
        line(f'{_format_clp(total_clp)} CLP', 330, 315, 'F2', 22, '1 1 1'),
        line(
            f'Tasa utilizada: 1 USD = ${USD_TO_CLP:,.0f} CLP',
            330, 296, 'F1', 8, '0.84 0.88 0.88'
        ),
        line(
            'El valor final puede variar segun las condiciones comerciales y de transporte.',
            42, 245, 'F1', 8, '0.40 0.46 0.48'
        ),
        box(42, 72, 528, 1, '0.95 0.44 0.13'),
        line('CINTAC | Cotizador de transporte', 42, 52, 'F2', 9, '0.11 0.19 0.23'),
        line('www.cintac.cl', 470, 52, 'F1', 8, '0.40 0.46 0.48'),
    ]
    stream = '\n'.join(stream_lines).encode('latin-1', errors='replace')

    objects = [
        b'<< /Type /Catalog /Pages 2 0 R >>',
        b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
        b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] '
        b'/Resources << /Font << /F1 4 0 R /F2 5 0 R >> >> /Contents 6 0 R >>',
        b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
        b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>',
        b'<< /Length ' + str(len(stream)).encode('ascii') + b' >>\nstream\n'
        + stream + b'\nendstream',
    ]
    pdf = bytearray(b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n')
    offsets = [0]
    for number, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f'{number} 0 obj\n'.encode('ascii'))
        pdf.extend(obj)
        pdf.extend(b'\nendobj\n')
    xref_offset = len(pdf)
    pdf.extend(f'xref\n0 {len(objects) + 1}\n'.encode('ascii'))
    pdf.extend(b'0000000000 65535 f \n')
    for offset in offsets[1:]:
        pdf.extend(f'{offset:010d} 00000 n \n'.encode('ascii'))
    pdf.extend(
        f'trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n'
        f'startxref\n{xref_offset}\n%%EOF\n'.encode('ascii')
    )
    return bytes(pdf)


def login(request):
    error = request.session.pop('login_error', None)

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        account = Login.objects.filter(
            username=username,
            password=password,
        ).first()

        if account is not None:
            request.session['login_id'] = account.pk
            return redirect('cotizador')

        return render(
            request,
            'Cotizador/login.html',
            {'error': 'Usuario o contraseña incorrectos.'},
        )

    return render(request, 'Cotizador/login.html', {'error': error})


def logout(request):
    request.session.flush()
    return redirect('login')


def Cotizador(request):
    login_id = request.session.get('login_id')
    if login_id is None or not Login.objects.filter(pk=login_id).exists():
        request.session.pop('login_id', None)
        request.session['login_error'] = (
            'Debes iniciar sesión para acceder al cotizador.'
        )
        return redirect('login')

    rutas = ruta_logistica.objects.order_by('puerto_origen', 'puerto_destino')
    puertos_origen = (
        ruta_logistica.objects.values_list('puerto_origen', flat=True)
        .distinct()
        .order_by('puerto_origen')
    )
    puertos_destino = (
        ruta_logistica.objects.values_list('puerto_destino', flat=True)
        .distinct()
        .order_by('puerto_destino')
    )
    context = {
        'rutas': rutas,
        'puertos_origen': puertos_origen,
        'puertos_destino': puertos_destino,
    }

    if request.method == 'POST':
        nombre_cliente = request.POST.get('nombre_cliente', '').strip()
        empresa = request.POST.get('empresa', '').strip()
        correo_cliente = request.POST.get('correo_cliente', '').strip()
        origen = request.POST.get('puerto_origen', '')
        destino = request.POST.get('puerto_destino', '')
        descripcion = request.POST.get('descripcion_carga', '').strip()
        peso = request.POST.get('peso_carga', '').strip()
        valor_carga = request.POST.get('valor_carga', '').strip()

        try:
            valida_nombre(nombre_cliente)
            valida_empresa(empresa)
            validate_login_email(correo_cliente)
        except ValidationError as error:
            context['error'] = error.messages[0]
            context['form_data'] = request.POST
            return render(request, 'Cotizador/cotizador.html', context)

        try:
            peso_carga = int(peso)
            if peso_carga <= 0:
                raise ValueError
        except (TypeError, ValueError):
            context['error'] = 'Ingresa un peso de carga válido mayor que cero.'
            context['form_data'] = request.POST
            return render(request, 'Cotizador/cotizador.html', context)

        if valor_carga:
            try:
                valor_carga_ingresado = int(valor_carga)
                if valor_carga_ingresado < 0:
                    raise ValueError
            except (TypeError, ValueError):
                context['error'] = 'Ingresa un valor de carga válido.'
                context['form_data'] = request.POST
                return render(request, 'Cotizador/cotizador.html', context)
        else:
            valor_carga_ingresado = None

        if (
            (origen in ORIGENES_CON_DESTINO_CALLAO and destino != DESTINO_CALLAO)
            or (
                origen not in ORIGENES_CON_DESTINO_CALLAO
                and destino == DESTINO_CALLAO
            )
        ):
            context['error'] = (
                'La combinación de puerto de origen y destino no es válida.'
            )
            context['form_data'] = request.POST
            return render(request, 'Cotizador/cotizador.html', context)

        ruta = ruta_logistica.objects.filter(
            puerto_origen=origen,
            puerto_destino=destino,
        ).first()
        tarifas = (
            tarifa_contenedor.objects.filter(
                id_ruta=ruta,
                tipo_contenedor__in=('20 HQ', '40 HQ'),
            )
            if ruta is not None
            else tarifa_contenedor.objects.none()
        )
        tarifas_por_tipo = {
            tarifa.tipo_contenedor: tarifa
            for tarifa in tarifas
        }

        if ruta is None or set(tarifas_por_tipo) != {'20 HQ', '40 HQ'}:
            context['error'] = (
                'No existen tarifas para contenedores 20 HQ y 40 HQ en la ruta seleccionada.'
            )
            context['form_data'] = request.POST
            return render(request, 'Cotizador/cotizador.html', context)

        resultados = []
        for tipo_contenedor in ('20 HQ', '40 HQ'):
            tarifa = tarifas_por_tipo[tipo_contenedor]
            cantidad = ceil(peso_carga / tarifa.peso_max)
            costo_fijo = Decimal(tarifa.costo_fijo) * cantidad
            monto_iva = (costo_fijo * Decimal('0.19')).quantize(Decimal('0.01'))
            monto_total = costo_fijo + monto_iva
            resultados.append({
                'ruta': ruta,
                'nombre_cliente': nombre_cliente,
                'empresa': empresa,
                'correo_cliente': correo_cliente,
                'tipo_contenedor': tarifa.tipo_contenedor,
                'descripcion_carga': descripcion,
                'peso_carga': peso_carga,
                'valor_carga': valor_carga_ingresado,
                'valor_carga_formateado': _format_clp(valor_carga_ingresado),
                'peso_max': tarifa.peso_max,
                'cantidad_contenedores': cantidad,
                'costo_fijo': costo_fijo,
                'monto_iva': monto_iva,
                'monto_total': monto_total,
                'moneda': tarifa.moneda_original,
            })
        context['resultados'] = resultados
        request.session['cotizaciones_pendientes'] = [
            {
                'nombre_cliente': resultado['nombre_cliente'],
                'empresa': resultado['empresa'],
                'correo_cliente': resultado['correo_cliente'],
                'descripcion_carga': resultado['descripcion_carga'],
                'peso_ingresado_kg': resultado['peso_carga'],
                'valor_carga_kg': resultado['valor_carga'],
                'tipo_contenedor': resultado['tipo_contenedor'],
                'cantidad_contenedores': resultado['cantidad_contenedores'],
                'id_ruta': ruta.pk,
                'puerto_origen': ruta.puerto_origen,
                'puerto_destino': ruta.puerto_destino,
                'monto_IVA': str(resultado['monto_iva']),
                'monto_total': str(resultado['monto_total']),
                'costo_fijo': str(resultado['costo_fijo']),
                'moneda': resultado['moneda'],
                'usuario': Login.objects.get(pk=login_id).username,
            }
            for resultado in resultados
        ]
        context['form_data'] = request.POST

    return render(request, 'Cotizador/cotizador.html', context)


def informe(request):
    login_id = request.session.get('login_id')
    if login_id is None or not Login.objects.filter(pk=login_id).exists():
        request.session.pop('login_id', None)
        request.session['login_error'] = (
            'Debes iniciar sesión para acceder al informe.'
        )
        return redirect('login')

    cotizaciones = request.session.get('cotizaciones_pendientes', [])
    context = {}

    if not cotizaciones:
        context['error'] = (
            'Primero debes calcular una cotización antes de generar el informe.'
        )
        return render(request, 'Cotizador/informe.html', context)

    if request.method == 'POST':
        tipo_contenedor = request.POST.get('tipo_contenedor', '')
        cotizacion = next(
            (
                item for item in cotizaciones
                if item['tipo_contenedor'] == tipo_contenedor
            ),
            None,
        )
        if cotizacion is None:
            return JsonResponse(
                {'error': 'La cotización seleccionada no está disponible.'},
                status=400,
            )
        try:
            registro = cotizacion_generada(
                id_ruta_id=cotizacion['id_ruta'],
                id_usuario_id=login_id,
                nombre_cliente=cotizacion['nombre_cliente'],
                empresa=cotizacion['empresa'],
                correo_cliente=cotizacion['correo_cliente'],
                descripcion_carga=cotizacion['descripcion_carga'],
                peso_ingresado_kg=cotizacion['peso_ingresado_kg'],
                valor_carga_kg=cotizacion['valor_carga_kg'],
                tipo_contenedor=cotizacion['tipo_contenedor'],
                cantidad_contenedores=cotizacion['cantidad_contenedores'],
                monto_IVA=int(Decimal(cotizacion['monto_IVA'])),
                monto_total=int(Decimal(cotizacion['monto_total'])),
            )
            registro.full_clean()
            registro.save()
        except ValidationError as error:
            return JsonResponse({'error': error.messages[0]}, status=400)

        request.session.pop('cotizaciones_pendientes', None)
        pdf = _build_quote_pdf(cotizacion, registro)
        response = HttpResponse(pdf, content_type='application/pdf')
        filename = (
            f'Cotizacion {_safe_filename(cotizacion["nombre_cliente"])} '
            f'{registro.fecha:%d-%m-%Y}.pdf'
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    return render(request, 'Cotizador/informe.html', context)

def historial(request):
    login_id = request.session.get('login_id')
    if login_id is None or not Login.objects.filter(pk=login_id).exists():
        request.session.pop('login_id', None)
        request.session['login_error'] = (
            'Debes iniciar sesión para acceder al historial.'
        )
        return redirect('login')

    historial_cotizaciones = (
        cotizacion_generada.objects.select_related('id_ruta')
        .order_by('-fecha')
    )
    for cotizacion in historial_cotizaciones:
        cotizacion.valor_carga_formateado = _format_clp(
            cotizacion.valor_carga_kg
        )

    context = {
        'historial_cotizaciones': historial_cotizaciones,
    }

    return render(request, 'Cotizador/historial.html', context)

def crear(request):
    login_id = request.session.get('login_id')
    if login_id is None or not Login.objects.filter(pk=login_id).exists():
        request.session.pop('login_id', None)
        request.session['login_error'] = (
            'Debes iniciar sesión para acceder a la creación de rutas.'
        )
        return redirect('login')

    form = CrearRutaForm(request.POST or None)
    context = {'form': form}

    if request.method == 'POST' and form.is_valid():
        context['created_route'] = form.save()
        context['success'] = 'La ruta y sus tarifas fueron creadas correctamente.'
        context['form'] = CrearRutaForm()

    return render(request, 'CRUD/crear.html', context)