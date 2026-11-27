from decimal import Decimal, InvalidOperation
from math import ceil
import re

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from .dolar import obtener_dolar
from django.utils import timezone
from .pdf import generar_cotizacion_pdf, numero
from .forms import CostosAdicionalesForm, CrearRutaForm, FiltrosHistorialForm
from .models import (
    Login,
    cotizacion_generada,
    ruta_logistica,
    tarifa_contenedor,
    validate_login_email,
    valida_empresa,
    valida_nombre,
)

TASA_HISTORICA = Decimal('950')

def _safe_filename(value):
    return re.sub(r'[<>:"/\\|?*]+', '', str(value)).strip()


def _format_clp(value):
    if value is None:
        return 'No ingresado'
    return f'${value:,.0f}'.replace(',', '.')

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
    dolar = obtener_dolar()
    adicionales = CostosAdicionalesForm(request.POST if request.method == 'POST' else None)
    context = {
        'adicionales': adicionales,
        'dolar': dolar,
        'valor_dolar': numero(dolar.valor, 2) if dolar else None,
        'dolar_anterior': dolar and dolar.fecha < timezone.localdate(),
        'operaciones': ['Importación', 'Exportación'],
        'rutas_disponibles': [
            {'operacion': ruta.operacion, 'origen': ruta.origen_visible,
             'destino': ruta.puerto_destino}
            for ruta in rutas if ruta.operacion
        ],
    }

    tarifas_por_ruta = {}
    tarifas = tarifa_contenedor.objects.filter(tipo_contenedor__in=('20 HQ', '40 HQ')).select_related('id_ruta').order_by(
        'id_ruta__puerto_origen', 'id_ruta__puerto_destino', 'tipo_contenedor', 'pk'
    )
    for tarifa in tarifas:
        ruta = tarifa.id_ruta
        if ruta.operacion:
            fila = tarifas_por_ruta.setdefault(ruta.pk, {'ruta': ruta})
            simbolo = '$' if tarifa.moneda_original == 'USD' else ''
            fila['precio_20' if tarifa.tipo_contenedor == '20 HQ' else 'precio_40'] = (
                f'{tarifa.moneda_original} {simbolo}{tarifa.costo_fijo:,}'.replace(',', '.')
            )
    context['tarifas_actuales'] = tarifas_por_ruta.values()

    if request.method == 'POST':
        if not adicionales.is_valid():
            context['form_data'] = request.POST
            return render(request, 'Cotizador/cotizador.html', context)
        flete_local = adicionales.cleaned_data['flete_local'] or Decimal('0')
        gastos_portuarios = adicionales.cleaned_data['gastos_portuarios'] or Decimal('0')
        tasa = dolar.valor if dolar else None
        fecha_tasa = dolar.fecha if dolar else None
        entrada = request.POST.get('tasa_manual', '').strip()
        if entrada:
            # Acepta 1044,08, 1.044,08 y 1044.08; un punto de miles indica pesos enteros.
            if re.fullmatch(r'[0-9]{1,3}(?:\.[0-9]{3})+(?:,[0-9]{1,2})?', entrada):
                entrada = entrada.replace('.', '')
            if not re.fullmatch(r'[0-9]{1,10}(?:[.,][0-9]{1,2})?', entrada) or Decimal(entrada.replace(',', '.')) <= 0:
                context.update(form_data=request.POST, error_manual='Ingresa una tasa positiva con hasta dos decimales.')
                return render(request, 'Cotizador/cotizador.html', context)
            tasa = Decimal(entrada.replace(',', '.'))
            fecha_tasa = timezone.localdate()
            context['tasa_manual_aplicada'] = numero(tasa, 2)
        nombre_cliente = request.POST.get('nombre_cliente', '').strip()
        empresa = request.POST.get('empresa', '').strip()
        correo_cliente = request.POST.get('correo_cliente', '').strip()
        origen = request.POST.get('puerto_origen', '')
        destino = request.POST.get('puerto_destino', '')
        descripcion = request.POST.get('descripcion_carga', '').strip()
        peso = request.POST.get('peso_carga', '').strip()
        unidad_peso = request.POST.get('unidad_peso', 'kg')
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
            peso_ingresado = Decimal(peso)
            if unidad_peso not in {'kg', 'ton'} or peso_ingresado <= 0:
                raise ValueError
            if unidad_peso == 'kg' and peso_ingresado != peso_ingresado.to_integral_value():
                raise ValueError
            peso_carga = int(
                peso_ingresado * (Decimal('1000') if unidad_peso == 'ton' else 1)
            )
            if peso_carga <= 0:
                raise ValueError
        except (InvalidOperation, TypeError, ValueError):
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

        ruta = next((ruta for ruta in rutas
                     if ruta.origen_visible == origen and ruta.puerto_destino == destino
                     and ruta.operacion and ruta.operacion == request.POST.get('operacion')), None)
        if ruta is None:
            context['error'] = 'Selecciona una ruta válida para la operación elegida.'
            context['form_data'] = request.POST
            return render(request, 'Cotizador/cotizador.html', context)

        tarifas = (
            tarifa_contenedor.objects.filter(
                id_ruta=ruta,
                tipo_contenedor__in=('20 HQ', '40 HQ'),
            )
        )
        tarifas_por_tipo = {
            tarifa.tipo_contenedor: tarifa
            for tarifa in tarifas
        }

        if set(tarifas_por_tipo) != {'20 HQ', '40 HQ'}:
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
            monto_total = costo_fijo + monto_iva + flete_local + gastos_portuarios
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
                'flete_local': flete_local,
                'gastos_portuarios': gastos_portuarios,
                'monto_iva': monto_iva,
                'monto_total': monto_total,
                'total_clp': _format_clp(monto_total * tasa) if tasa else None,
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
                'tasa_usd_clp': str(tasa) if tasa else None,
                'dolar_manual': bool(entrada),
                'fecha_dolar': fecha_tasa.isoformat() if fecha_tasa else None,
                'dias_transito': ruta.dias_transito,
                'peso_max': resultado['peso_max'],
                'puerto_origen': ruta.puerto_origen,
                'puerto_destino': ruta.puerto_destino,
                'monto_IVA': str(resultado['monto_iva']),
                'monto_total': str(resultado['monto_total']),
                'costo_fijo': str(resultado['costo_fijo']),
                'flete_local': str(flete_local),
                'gastos_portuarios': str(gastos_portuarios),
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
                tasa_usd_clp=cotizacion.get('tasa_usd_clp', TASA_HISTORICA),
                fecha_dolar=cotizacion.get('fecha_dolar'),
                dolar_manual=cotizacion.get('dolar_manual', False),
                id_usuario_id=login_id,
                nombre_cliente=cotizacion['nombre_cliente'],
                empresa=cotizacion['empresa'],
                correo_cliente=cotizacion['correo_cliente'],
                descripcion_carga=cotizacion['descripcion_carga'],
                peso_ingresado_kg=cotizacion['peso_ingresado_kg'],
                valor_carga_kg=cotizacion['valor_carga_kg'],
                tipo_contenedor=cotizacion['tipo_contenedor'],
                cantidad_contenedores=cotizacion['cantidad_contenedores'],
                flete_local=cotizacion.get('flete_local', 0),
                gastos_portuarios=cotizacion.get('gastos_portuarios', 0),
                monto_IVA=Decimal(cotizacion['monto_IVA']),
                monto_total=Decimal(cotizacion['monto_total']),
            )
            registro.full_clean()
            with transaction.atomic():
                registro.save()
                registro.comprobante_pdf = generar_cotizacion_pdf(cotizacion, registro, registro.tasa_usd_clp)
                registro.save(update_fields=['comprobante_pdf'])
        except ValidationError as error:
            return JsonResponse({'error': error.messages[0]}, status=400)

        request.session.pop('cotizaciones_pendientes', None)
        response = HttpResponse(registro.comprobante_pdf, content_type='application/pdf')
        filename = (
            f'Cotizacion {_safe_filename(cotizacion["nombre_cliente"])} '
            f'{timezone.localdate(registro.fecha):%d-%m-%Y}.pdf'
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
        cotizacion_generada.objects.defer('comprobante_pdf').select_related('id_ruta', 'id_usuario')
        .order_by('-fecha')
    )
    filtros = FiltrosHistorialForm(request.GET)
    if filtros.is_valid():
        datos = filtros.cleaned_data
        for campo, filtro in [('id', 'pk'), ('ruta', 'id_ruta'), ('desde', 'fecha__date__gte'),
                              ('hasta', 'fecha__date__lte')]:
            if datos[campo]:
                historial_cotizaciones = historial_cotizaciones.filter(**{filtro: datos[campo]})
        if datos['cliente']:
            historial_cotizaciones = historial_cotizaciones.filter(
                Q(nombre_cliente__icontains=datos['cliente']) | Q(empresa__icontains=datos['cliente'])
            )
        if datos['operacion']:
            rutas = filtros.fields['ruta'].queryset
            ids = [ruta.pk for ruta in rutas if ruta.operacion == datos['operacion']]
            historial_cotizaciones = historial_cotizaciones.filter(id_ruta_id__in=ids)
    else:
        historial_cotizaciones = historial_cotizaciones.none()

    for cotizacion in historial_cotizaciones:
        cotizacion.valor_carga_formateado = _format_clp(
            cotizacion.valor_carga_kg
        )

    context = {
        'historial_cotizaciones': historial_cotizaciones,
        'filtros': filtros,
        'busqueda_activa': any(request.GET.get(campo) for campo in filtros.fields),
    }

    return render(request, 'Cotizador/historial.html', context)

def detalle_cotizacion(request, cotizacion_id):
    if not Login.objects.filter(pk=request.session.get('login_id')).exists():
        return redirect('login')

    registro = get_object_or_404(
        cotizacion_generada.objects.select_related('id_ruta', 'id_usuario'),
        pk=cotizacion_id,
    )
    pdf = registro.comprobante_pdf
    if not pdf:
        datos = {
            campo: getattr(registro, campo) for campo in (
                'nombre_cliente', 'empresa', 'correo_cliente', 'descripcion_carga',
                'tipo_contenedor', 'cantidad_contenedores', 'peso_ingresado_kg',
                'valor_carga_kg', 'monto_IVA', 'monto_total',
            )
        }
        datos.update(
            titulo='COTIZACION | COPIA DEL REGISTRO HISTORICO',
            usuario=registro.id_usuario.username,
            puerto_destino=registro.id_ruta.puerto_destino,
            costo_fijo=registro.monto_total - registro.monto_IVA - registro.flete_local - registro.gastos_portuarios,
        )
        pdf = generar_cotizacion_pdf(datos, registro, registro.tasa_usd_clp)

    response = HttpResponse(bytes(pdf), content_type='application/pdf')
    modo = 'attachment' if request.GET.get('descargar') == '1' else 'inline'
    response['Content-Disposition'] = f'{modo}; filename="Cotizacion-{registro.pk}.pdf"'
    response['Cache-Control'] = 'private, no-store'
    return response


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

def editar(request, ruta_id=None):
    login_id = request.session.get('login_id')
    if login_id is None or not Login.objects.filter(pk=login_id).exists():
        request.session.pop('login_id', None)
        request.session['login_error'] = (
            'Debes iniciar sesión para acceder a la edición de rutas.'
        )
        return redirect('login')

    rutas = ruta_logistica.objects.order_by('puerto_origen', 'puerto_destino')
    if ruta_id is None:
        selected_route_id = request.GET.get('ruta_id')
        if selected_route_id:
            try:
                ruta_id = int(selected_route_id)
            except (TypeError, ValueError):
                return render(request, 'CRUD/editar.html', {
                    'rutas': rutas,
                    'error': 'Selecciona una ruta válida para editar.',
                })
        else:
            return render(request, 'CRUD/editar.html', {'rutas': rutas})

    ruta = ruta_logistica.objects.filter(pk=ruta_id).first()
    if ruta is None:
        return render(request, 'CRUD/editar.html', {
            'rutas': rutas,
            'error': 'La ruta especificada no existe.',
        })

    form = CrearRutaForm(request.POST or None, instance=ruta)
    context = {
        'form': form,
        'ruta': ruta,
        'rutas': rutas,
        'selected_route_id': ruta_id,
    }

    if request.method == 'POST' and form.is_valid():
        context['updated_route'] = form.save()
        context['success'] = 'Se ha actualizado la ruta'
        context['form'] = None
        context['selected_route_id'] = None

    return render(request, 'CRUD/editar.html', context)

def eliminar(request, ruta_id=None):
    login_id = request.session.get('login_id')
    if login_id is None or not Login.objects.filter(pk=login_id).exists():
        request.session.pop('login_id', None)
        request.session['login_error'] = (
            'Debes iniciar sesión para acceder a la eliminación de rutas.'
        )
        return redirect('login')

    rutas = ruta_logistica.objects.order_by('puerto_origen', 'puerto_destino')

    if ruta_id is None and request.method == 'POST':
        selected_route_id = request.POST.get('ruta_id', '')
        try:
            ruta_id = int(selected_route_id)
        except (TypeError, ValueError):
            return render(request, 'CRUD/eliminar.html', {
                'rutas': rutas,
                'error': 'Selecciona una ruta válida para eliminar.',
            })

    if ruta_id is None:
        return render(request, 'CRUD/eliminar.html', {'rutas': rutas})

    ruta = get_object_or_404(ruta_logistica, pk=ruta_id)
    if request.method == 'POST':
        deleted_route = (
            f'{ruta.puerto_origen} → {ruta.puerto_destino}'
        )
        ruta.delete()
        return render(request, 'CRUD/eliminar.html', {
            'rutas': ruta_logistica.objects.order_by(
                'puerto_origen', 'puerto_destino'
            ),
            'success': 'La ruta fue eliminada correctamente.',
            'deleted_route': deleted_route,
        })

    return render(request, 'CRUD/eliminar.html', {
        'rutas': rutas,
        'selected_route_id': ruta_id,
    })