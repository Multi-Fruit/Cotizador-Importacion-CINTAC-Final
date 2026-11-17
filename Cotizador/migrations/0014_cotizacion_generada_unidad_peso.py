from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Cotizador', '0013_alter_ruta_logistica_puerto_destino_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='cotizacion_generada',
            name='unidad_peso',
            field=models.CharField(
                choices=[('kg', 'Kilogramos'), ('t', 'Toneladas')],
                default='kg',
                max_length=2,
            ),
        ),
    ]
