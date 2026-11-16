from decimal import Decimal

from django import forms
from django.db import transaction

from .models import ruta_logistica, tarifa_contenedor


class CrearRutaForm(forms.Form):
    puerto_origen = forms.CharField(
        label='Puerto de origen',
        max_length=100,
    )
    puerto_destino = forms.ChoiceField(
        label='Puerto de destino',
        choices=(
            ('Valparaiso, Chile', 'Valparaiso, Chile'),
            ('San Antonio, Chile', 'San Antonio, Chile'),
        ),
    )
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'route-form-control'

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
        return cleaned_data

    def save(self):
        data = self.cleaned_data
        puerto_destino = data['puerto_destino']
        if puerto_destino == 'Valparaiso, Chile':
            puerto_destino = 'Valparaíso, Chile'

        with transaction.atomic():
            ruta, _ = ruta_logistica.objects.get_or_create(
                puerto_origen=data['puerto_origen'],
                puerto_destino=puerto_destino,
                defaults={'dias_transito': data['dias_transito']},
            )
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