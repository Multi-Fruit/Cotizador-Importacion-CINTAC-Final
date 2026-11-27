from decimal import Decimal

from django import forms
from django.db import transaction
from .models import ruta_logistica, tarifa_contenedor


class CrearRutaForm(forms.Form):
    operacion = forms.ChoiceField(
        choices=[(tipo, tipo) for tipo in ('Importación', 'Exportación')],
        widget=forms.RadioSelect,
    )
    puerto_origen = forms.CharField(
        label='Puerto de origen',
        max_length=100,
    )
    puerto_destino = forms.CharField(label='Puerto de destino', max_length=100)
    dias_transito = forms.IntegerField(
        label='Días de tránsito estimados',
        min_value=1,
    )
    peso_max_20hq = forms.IntegerField(
        label='Peso máximo 20HQ (kg)',
        min_value=1,
        widget=forms.Select(choices=((23000, '23000'),)),
    )
    costo_fijo_20hq = forms.DecimalField(
        label='Costo fijo 20HQ (USD)',
        min_value=Decimal('0'),
        decimal_places=0,
        max_digits=10,
    )
    peso_max_40hq = forms.IntegerField(
        label='Peso máximo 40HQ (kg)',
        min_value=1,
        widget=forms.Select(choices=((25000, '25000'),)),
    )
    costo_fijo_40hq = forms.DecimalField(
        label='Costo fijo 40HQ (USD)',
        min_value=Decimal('0'),
        decimal_places=0,
        max_digits=10,
    )

    def __init__(self, *args, instance=None, **kwargs):
        self.instance = instance
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'route-form-control'

        if instance is not None:
            del self.fields['operacion']
            self.fields['puerto_origen'].disabled = True
            self.fields['puerto_origen'].label = 'Puerto de origen (no editable)'
            self.fields['puerto_destino'].disabled = True
            self.fields['puerto_destino'].label = 'Puerto de destino (no editable)'
            self.initial['puerto_origen'] = instance.puerto_origen
            puerto_destino = instance.puerto_destino
            self.initial['puerto_destino'] = puerto_destino

        if instance is not None and not self.is_bound:
            tarifas = {
                tarifa.tipo_contenedor: tarifa
                for tarifa in tarifa_contenedor.objects.filter(
                    id_ruta=instance,
                    tipo_contenedor__in=('20 HQ', '40 HQ'),
                )
            }
            tarifa_20hq = tarifas.get('20 HQ')
            tarifa_40hq = tarifas.get('40 HQ')

            self.initial.update({
                'puerto_origen': instance.puerto_origen,
                'puerto_destino': puerto_destino,
                'dias_transito': instance.dias_transito,
                'peso_max_20hq': (
                    tarifa_20hq.peso_max if tarifa_20hq is not None else None
                ),
                'costo_fijo_20hq': (
                    tarifa_20hq.costo_fijo if tarifa_20hq is not None else None
                ),
                'peso_max_40hq': (
                    tarifa_40hq.peso_max if tarifa_40hq is not None else None
                ),
                'costo_fijo_40hq': (
                    tarifa_40hq.costo_fijo if tarifa_40hq is not None else None
                ),
            })

    def clean(self):
        cleaned_data = super().clean()
        if (
            cleaned_data.get('puerto_origen')
            and cleaned_data.get('puerto_destino')
            and cleaned_data['puerto_origen'] == cleaned_data['puerto_destino']
        ):
            raise forms.ValidationError(
                'El puerto de origen y destino no pueden ser iguales.'
            )
        if self.instance is None and all(cleaned_data.get(campo) for campo in (
            'operacion', 'puerto_origen', 'puerto_destino'
        )):
            origen = cleaned_data['puerto_origen']
            for puerto in ('San Antonio', 'Valparaíso'):
                variantes = {puerto.casefold(), puerto.casefold().replace('í', 'i')}
                if origen.casefold().removesuffix(', chile') in variantes:
                    origen = f'{puerto}, Chile'
                    break
            ruta = ruta_logistica(puerto_origen=origen, puerto_destino=cleaned_data['puerto_destino'])
            if ruta.operacion != cleaned_data['operacion']:
                raise forms.ValidationError('Selecciona puertos válidos para la operación elegida.')
            if ruta.operacion == 'Exportación':
                if ruta_logistica.objects.filter(
                    puerto_origen__iexact=origen, puerto_destino__iexact=ruta.puerto_destino
                ).exists():
                    raise forms.ValidationError('Esta ruta de exportación ya existe. Puedes modificar sus tarifas en Editar ruta.')
                # Conserva el valor interno definido en las opciones del modelo.
                origen = next(valor for valor, _ in ruta.PUERTOS_ORIGEN if valor.casefold() == origen.casefold())
            cleaned_data['puerto_origen'] = origen
        return cleaned_data

    def save(self):
        data = self.cleaned_data
        puerto_destino = data['puerto_destino']
        if puerto_destino == 'Valparaiso, Chile':
            puerto_destino = 'Valparaíso, Chile'

        with transaction.atomic():
            if self.instance is None:
                ruta, _ = ruta_logistica.objects.get_or_create(
                    puerto_origen=data['puerto_origen'],
                    puerto_destino=puerto_destino,
                    defaults={'dias_transito': data['dias_transito']},
                )
            else:
                ruta = self.instance
            ruta.puerto_origen = data['puerto_origen']
            ruta.puerto_destino = puerto_destino
            ruta.dias_transito = data['dias_transito']
            ruta.save()

            tarifa_contenedor.objects.update_or_create(
                id_ruta=ruta,
                tipo_contenedor='20 HQ',
                defaults={
                    'peso_max': data['peso_max_20hq'],
                    'costo_fijo': int(data['costo_fijo_20hq']),
                    'moneda_original': 'USD',
                },
            )
            tarifa_contenedor.objects.update_or_create(
                id_ruta=ruta,
                tipo_contenedor='40 HQ',
                defaults={
                    'peso_max': data['peso_max_40hq'],
                    'costo_fijo': int(data['costo_fijo_40hq']),
                    'moneda_original': 'USD',
                },
            )

        return ruta


class RutaHistorialField(forms.ModelChoiceField):
    def label_from_instance(self, ruta):
        return f'{ruta.origen_visible} → {ruta.puerto_destino}'


class FiltrosHistorialForm(forms.Form):
    id = forms.IntegerField(label='ID de cotización', min_value=1, max_value=2147483647, required=False)
    cliente = forms.CharField(label='Cliente o empresa', max_length=100, required=False)
    ruta = RutaHistorialField(
        label='Ruta', empty_label='Todas las rutas', required=False,
        queryset=ruta_logistica.objects.filter(cotizacion_generada__isnull=False)
        .distinct().order_by('puerto_origen', 'puerto_destino'),
    )
    operacion = forms.ChoiceField(label='Operación', required=False, choices=[
        ('', 'Todas las operaciones'), ('Importación', 'Importación'), ('Exportación', 'Exportación'),
    ])
    desde = forms.DateField(label='Desde', required=False, input_formats=['%Y-%m-%d'],
                            widget=forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'))
    hasta = forms.DateField(label='Hasta', required=False, input_formats=['%Y-%m-%d'],
                            widget=forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'))

    def clean(self):
        datos = super().clean()
        if datos.get('desde') and datos.get('hasta') and datos['desde'] > datos['hasta']:
            self.add_error('hasta', 'La fecha final debe ser igual o posterior a la inicial.')
        return datos

class CostosAdicionalesForm(forms.Form):
    flete_local = forms.DecimalField(label='Flete local (USD)', required=False,
                                     min_value=0, max_digits=12, decimal_places=2)
    gastos_portuarios = forms.DecimalField(label='Gastos portuarios (USD)', required=False,
                                           min_value=0, max_digits=12, decimal_places=2)
