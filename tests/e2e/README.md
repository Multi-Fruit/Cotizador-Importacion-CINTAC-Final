# Pruebas E2E

La cobertura de las 21 filas del Excel Grupo 7, sus discrepancias y el comando
de concurrencia están en [PLANILLA.md](PLANILLA.md).

Desde la raíz, activar `.venv` (PowerShell: `.venv\Scripts\Activate.ps1`).
Se mantiene pip y requirements-dev.txt, sin otro gestor de dependencias.

```powershell
python -m pip install -r requirements-dev.txt
python -m playwright install chromium
python -m pytest tests/e2e -q
python -m pytest tests/e2e/test_calculator.py::test_breakdown_and_recalculation -q
python -m pytest tests/e2e/test_calculator.py::test_breakdown_and_recalculation --headed --slowmo 300
python -m pytest -q
```

El último comando incluye las pruebas existentes de `Cotizador/tests.py`, sin
reemplazarlas. En Linux para instalar también bibliotecas del navegador:
`python -m playwright install --with-deps chromium`.
Para usar el inspector en PowerShell:

```powershell
$env:PWDEBUG = '1'
python -m pytest tests/e2e/test_calculator.py::test_breakdown_and_recalculation -s
Remove-Item Env:PWDEBUG
```

Chromium corre sin interfaz por defecto. Ante fallos, pytest-playwright conserva
capturas y trazas en `artifacts/e2e/<prueba>/`. Para abrir una traza:
`python -m playwright show-trace artifacts/e2e/<prueba>/trace.zip`.
Cada ejecución reemplaza la salida anterior; copiar los artefactos antes de
repetir una ejecución que se quiera conservar. No hay pausas fijas en los tests.

## Aislamiento

`pytest.ini` selecciona `ProyectoFinal.settings_test`: SQLite en un directorio
temporal exclusivo, sin leer db.sqlite3, DATABASE_URL ni credenciales del proyecto. Django
crea las tablas mediante migraciones. `transactional_db` prepara un usuario
ficticio, una ruta y dos tarifas por prueba; `live_server` comparte esa base con
sus hilos HTTP con conexiones independientes y sirve los estáticos mediante pytest-django.
El archivo temporal evita compartir una sola conexión SQLite entre peticiones
concurrentes, como ocurría con la configuración previa en memoria. Django
elimina la base al terminar y TemporaryDirectory limpia el directorio. No iniciar runserver,
no cargar los JSON existentes y no pasar `--ds` apuntando a otra configuración.
Cada prueba tiene un contexto de navegador y sesión nuevos; Django limpia los
datos entre pruebas.

La API síncrona de Playwright mantiene un event loop: una fixture de sesión E2E
habilita temporalmente `DJANGO_ALLOW_ASYNC_UNSAFE` para las operaciones ORM
secuenciales de preparación y limpieza. No se configura en producción.

El tipo de cambio se fija en Decimal('950') mediante monkeypatch y las tarifas
proceden sólo de las fixtures. No existen APIs de tarifas o cambio en el código
actual. Las conexiones Python fuera de loopback fallan; el navegador permite
sólo el origen de live_server. Google Fonts se sustituye por CSS vacío local;
otras peticiones externas se bloquean y hacen fallar la prueba.

## Alcance y resultados independientes

La autenticación real usa `Login` y `session['login_id']`, no auth.User. El
formulario de cálculo se procesa directamente en views.py; CrearRutaForm es
para administración de rutas. La cantidad es el peso dividido por capacidad,
redondeado hacia arriba; el flete es tarifa por cantidad; IVA = 19% del flete.
El valor de carga opcional es informativo y no integra la base del IVA.
No existen seguro ni aranceles: no se inventan pruebas ni reglas para ellos.
La pantalla muestra USD; la conversión CLP se verifica en el PDF realmente
descargado haciendo clic en «Generar informe», que también guarda el registro.

| Caso | Flete USD | IVA USD | Total USD | CLP a 950 |
| --- | ---: | ---: | ---: | ---: |
| 24.000 kg / 20 HQ, capacidad 23.000, tarifa 1001 | 2002 | 380,38 | 2382,38 | 2.263.261 |
| 24.000 kg / 40 HQ, capacidad 25.000, tarifa 1500 | 1500 | 285 | 1785 | 1.695.750 |
| 25.001 kg / 40 HQ | 3000 | 570 | 3570 | — |
| 23.000 kg / 20 HQ | 1001 | 190,19 | 1191,19 | — |

Las expectativas son literales; no llaman funciones de cálculo ni formato de
producción. Se prueban login inválido/válido, protección de acceso y logout,
ambos desgloses, IVA, recálculo, kilos y toneladas con coma, conversión y descarga,
persistencia en historial tras recargar, valor opcional, campos obligatorios,
correo/peso/precio inválidos, límite máximo y precisión de peso. Un cálculo
inválido debe eliminar también el informe pendiente anterior.

## Defecto identificado y regla confirmada

El usuario confirmó que el historial debe redondear al entero más cercano, con
0,5 hacia arriba. Actualmente `informe()` usa `int(Decimal(...))` para IVA y total,
truncando los decimales. `test_history_rounds_total_half_up` documenta el defecto
como `xfail(strict=True)`: 46.001 kg / 20 HQ cuestan 3003 + 570,57 = 3573,57 USD;
el historial guarda 3573 cuando debería mostrar 3574. Es un fallo esperado,
no una prueba aprobada. Al corregir producción, el XPASS estricto obligará a
retirar la marca. No se modifica ninguna regla de negocio en esta entrega.

Además, los enlaces «Cerrar sesión» de historial/informe apuntan a login en vez
de logout; esto no invalida la sesión. La prueba de logout cubre el enlace del
cotizador. Las credenciales de Login se comparan en texto plano, pese a lo que
indica el README general. Se reportan estos hallazgos sin cambiarlos.

No se encontró configuración CI versionada; no se introduce un proveedor nuevo.
En una futura CI ejecutar instalación, `playwright install --with-deps chromium`
y `pytest tests/e2e`, y recoger `artifacts/e2e` incluso si falla el job.

## Ejecución verificada (16 de noviembre de 2026)

- Instalación de pytest, pytest-django, pytest-playwright y Chromium: completada.
  PyPI requirió acceso de red fuera del sandbox. `pip check`: sin conflictos.
- `python -m pytest tests/e2e -x -q`: 21 aprobadas antes de incorporar la
  regresión de redondeo confirmada por el usuario.
- `python -m pytest -q -rx --junitxml=artifacts/e2e-results.xml`: 40 aprobadas
  (21 E2E y 19 existentes), 1 fallo existente y 1 E2E xfail; 21 subtests aprobados.
- El fallo existente es
  `RutaLogisticaModelTests.test_puerto_origen_exposes_only_allowed_countries`:
  espera 14 puertos, pero el modelo incluye también dos puertos chilenos.
  Se reprodujo con `python -m pytest Cotizador/tests.py -q -x`.
- `python -m pytest tests/e2e/test_calculator.py::test_history_rounds_total_half_up --runxfail -q --output artifacts/e2e-rounding`:
  falla exactamente por mostrar $3573 en vez de $3574; captura y trace.zip
  comprobados en esa carpeta. Esto verifica también la captura ante fallos.
- El plugin emite un aviso de deprecación de fixture `base_url` con pytest 9;
  no impide ejecutar. No quedaron pruebas bloqueadas o sin ejecutar.

Para reproducir el defecto sin tratarlo como fallo esperado, usar el comando
`--runxfail` anterior. Los artefactos son locales e ignorados por Git.

Referencias: [live_server y transacciones](https://pytest-django.readthedocs.io/en/stable/database.html),
[opciones de pytest-playwright](https://playwright.dev/python/docs/test-runners).
