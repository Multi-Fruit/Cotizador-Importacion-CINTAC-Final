import json
import os
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from http.client import HTTPException
from urllib.parse import urlencode
from urllib.request import urlopen

from django.core.cache import cache
from django.utils import timezone

from .models import DolarObservado


def consultar_banco(token, hoy):
    parametros = urlencode({
        'token': token, 'function': 'GetSeries', 'timeseries': 'F073.TCO.PRE.Z.D',
        'firstdate': hoy - timedelta(days=30), 'lastdate': hoy,
    })
    with urlopen('https://si3.bcentral.cl/SieteRestWS/SieteRestWS.ashx?' + parametros,
                 timeout=4) as respuesta:
        datos = json.loads(respuesta.read().decode(respuesta.headers.get_content_charset() or 'utf-8'))
    if datos['Codigo'] != 0:
        return None
    observaciones = []
    for fila in datos['Series']['Obs']:
        if fila['statusCode'] == 'OK':
            fecha = datetime.strptime(fila['indexDateString'], '%d-%m-%Y').date()
            valor = Decimal(fila['value'])
            if fecha <= hoy and valor.is_finite() and 0 < valor < 10**10:
                observaciones.append((fecha, valor))
    return max(observaciones, default=None)


def obtener_dolar():
    hoy = timezone.localdate()
    ultimo = DolarObservado.objects.order_by('-fecha').first()
    token = os.environ.get('BCCH_API_TOKEN')
    if not token or (ultimo and ultimo.fecha == hoy):
        return ultimo
    if cache.add('bcch-consulta-' + hoy.isoformat(), True, timeout=300):
        try:
            dato = consultar_banco(token, hoy)
        except (OSError, HTTPException, ValueError, KeyError, TypeError, InvalidOperation):
            dato = None
        if dato and (not ultimo or dato[0] >= ultimo.fecha):
            ultimo, _ = DolarObservado.objects.update_or_create(fecha=dato[0], defaults={'valor': dato[1]})
    return ultimo
