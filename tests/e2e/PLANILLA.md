 Trazabilidad: Casos de prueba de software grupo 7.xlsx

Se leyó la hoja «Plantilla de Casos de Prueba», filas 7–27 (21 filas).
La hoja «Instrucciones» describe cómo rellenar la plantilla; no se tomó como
una orden para modificar producción. Los estados históricos no se copiaron
como resultados actuales. El archivo original permanece intacto.

P09 está repetido: se distingue por fila 15 (login) y fila 16 (contraseña).
P02/P03, P07/P08 y P13/P14 describen el mismo recorrido antes y después de
correcciones; comparten prueba, conservando la trazabilidad de ambas filas.
Los IDs P-18/P-19/P-20 se normalizan como P18/P19/P20 en los nombres Python.

## Matriz completa

Los nombres sin archivo pertenecen a `test_spreadsheet.py`.

| Fila | ID | Prueba automatizada | Resultado / alcance |
| --- | --- | --- | --- |
| 7 | P01 | `test_p01_p06_startup_and_login_form` | Arranque HTTP real y formulario inicial. El usuario confirmó que no incluye bloqueo tras tres intentos. |
| 8 | P02 | `test_p02_p03_home_link_to_login` | FALLA: la raíz es login; no existe enlace «Cotizador». |
| 9 | P03 | `test_p02_p03_home_link_to_login` | Mismo requisito de navegación, misma discrepancia. |
| 10 | P04 | `test_p04_superuser_access` | Comando createsuperuser no interactivo sobre DB de prueba, login admin y acceso a modelos. |
| 11 | P05 | `test_p05_p07_p08_p09_create_user_and_login` | Crear Login desde admin, persistir y comprobar rol automático. |
| 12 | P06 | `test_p01_p06_startup_and_login_form` | Campos y botón de inicio de sesión visibles y utilizables. |
| 13 | P07 | `test_p05_p07_p08_p09_create_user_and_login` | Cotizador accesible autenticado, también al recargar. |
| 14 | P08 | `test_p05_p07_p08_p09_create_user_and_login` | Comparte P07. Se usa la ruta vigente /Cotizador/cotizador/. |
| 15 | P09 | `test_p05_p07_p08_p09_create_user_and_login` | Inicio de sesión con usuario recién creado desde admin. |
| 16 | P09 | `test_admin_user_validation[P09-fila16-P10-*]` | Rechazo de contraseña corta, sin mayúscula o sin número. |
| 17 | P10 | `test_admin_user_validation[P09-fila16-P10-*]` | Mismo requisito; contraseña válida en P05/P09. |
| 18 | P11 | `test_admin_user_validation[P11-*]` | Rechazo de username corto, espacios y símbolos; válido con letras, números y guion bajo en P05. |
| 19 | P12 | `test_admin_user_validation[P12-*]` | Rechazo de correo sin @ o sin dominio completo; correo válido en P05. |
| 20 | P13 | `test_p13_p14_direct_access_is_denied` | Redirección al login sin sesión. |
| 21 | P14 | `test_p13_p14_direct_access_is_denied` | Comparte P13. |
| 22 | P15 | `test_p15_create_route_in_admin` | Alta real de ruta y consulta tras recargar, comprobación ORM. |
| 23 | P16 | `test_p16_create_tariff_in_admin` | Alta real de tarifa asociada a ruta y persistencia. |
| 24 | P17 | `test_p17_select_only_40hq_above_20_tonnes` | FALLA: muestra 20 HQ además de 40 HQ para 20.001 kg. Usuario confirmó mantener requisito literal. |
| 25 | P-18 | `test_p18_invalid_weight_browser_and_server` | -1500 y abc: validación HTML con mensaje; además POST sin validación HTML comprueba rechazo Django. |
| 26 | P-19 | `test_calculator.py::test_download_conversion_and_history` | Reutilizada y ampliada: descarga, marca/imagen corporativa, datos cliente/carga/ruta, USD y CLP en PDF real; ambos contenedores. |
| 27 | P-20 | `test_concurrency.py::test_p20_three_concurrent_sessions` | Variante local ejecutada; variante Neon omitida explícitamente sin entorno exclusivo de pruebas. |

Los fallos P02/P03 y P17 son fallos reales, no están marcados xfail ni se
cambió la aplicación para ocultarlos. El xfail de redondeo pertenece a la
entrega anterior y continúa separado.

P01 utiliza el servidor HTTP live_server en lugar de arrancar runserver
contra la DB local. P07/P08 respetan autenticación y capitalización actuales.
No se automatiza una aprobación visual subjetiva de los colores del PDF:
se verifica el archivo corporativo generado, su autor, imagen y contenido;
la planilla no especifica tolerancia visual ni colores exactos.

## Ejecución

```powershell
python -m pytest tests/e2e/test_spreadsheet.py tests/e2e/test_concurrency.py tests/e2e/test_calculator.py::test_download_conversion_and_history -q -rs --output artifacts/planilla --junitxml=artifacts/planilla.xml
python -m pytest tests/e2e/test_spreadsheet.py -k p17 --headed
python -m pytest -q -rx -rs --output artifacts/planilla-completa --junitxml=artifacts/planilla-completa.xml
```

Los comandos de instalación, inspector y trazas están en [README.md](README.md).
Las capturas/trazas de fallos quedan bajo la carpeta `--output` y se reemplazan
en la siguiente ejecución que use esa misma carpeta.

## P20: concurrencia y entorno Neon pendiente

Tres contextos independientes de Chromium ingresan con tres usuarios ficticios.
Cada navegador envía el formulario real con CSRF mediante fetch. Una barrera
en la entrada de la vista, exclusiva de la prueba, obliga a tener las tres
solicitudes en vuelo antes de ejecutar el código real. No hay sleeps ni se
mockea el cálculo. El presupuesto <2000 ms incluye espera en la barrera y
lectura de la respuesta, excluye login y preparación. Se verifican HTTP 200,
resultados distintos, tres sesiones persistidas sin mezcla de datos y sus
cotizaciones pendientes. Los tiempos se guardan como `response_times_ms` en
JUnit. El límite se evalúa, no se relaja si la máquina es lenta.

Esto es una muestra simultánea de tres usuarios, no una campaña sostenida de
carga. Calcular guarda la sesión; no crea cotizacion_generada hasta descargar
el informe. P19 cubre ese guardado. SQLite local no demuestra rendimiento ni
transaccionalidad de Neon.

La configuración de pruebas usa un archivo SQLite temporal por ejecución,
eliminado al terminar. Se sustituyó la base en memoria porque live_server
comparte su conexión entre hilos y produjo `InterfaceError` bajo concurrencia.
Con el archivo temporal cada hilo abre su propia conexión y se conserva el
aislamiento respecto de db.sqlite3. No se serializaron las peticiones para
hacer pasar el caso ni se cambió el motor de cálculo.


## Resultado final — 16 de noviembre de 2026

Ejecutado el comando de suite completa anterior, con Chromium sin interfaz:
**56 aprobadas, 3 fallidas, 1 xfail y 21 subtests aprobados**
en 146,49 segundos. De ellas, las E2E son 38 aprobadas, 2 fallidas, 1 omitida
y 1 xfail. Las 19 aprobadas y el fallo restantes pertenecen a las pruebas
existentes de Cotizador/tests.py.

- Fallo nuevo P02/P03: enlace «Cotizador» ausente en la raíz.
- Fallo nuevo P17: no descarta 20 HQ sobre 20.000 kg.
- Fallo existente: `RutaLogisticaModelTests.test_puerto_origen_exposes_only_allowed_countries`
  excluye dos puertos chilenos que el modelo actual incluye.
- Xfail existente: historial trunca en lugar de redondear según la regla confirmada.

Las pruebas muestran que las funciones principales del cotizador funcionan correctamente: ingresar al sistema, registrar información, calcular costos, generar informes y consultar cotizaciones guardadas.

Sin embargo, todavía hay aspectos por corregir: falta el enlace de acceso al cotizador desde la página inicial, la selección del contenedor no cumple lo esperado al superar las 20 toneladas y el historial debe aplicar el redondeo acordado. También existe una diferencia entre los puertos disponibles y los que espera una de las pruebas.
