
# 🚢 Cotizador Logístico Interno CINTAC

<div align="center">



![HTML5](https://img.shields.io/badge/html5-%23E34F26.svg?style=for-the-badge&logo=html5&logoColor=white)
![CSS3](https://img.shields.io/badge/css3-%231572B6.svg?style=for-the-badge&logo=css3&logoColor=white)
![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![Django](https://img.shields.io/badge/django-%23092E20.svg?style=for-the-badge&logo=django&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/Neon-PostgreSQL-336791?style=for-the-badge&logo=postgresql&logoColor=white)
![Vercel](https://img.shields.io/badge/Vercel-Cloud%20Hosting-000000?style=for-the-badge&logo=vercel&logoColor=white)

</div>



## Descripción

**Cotizador Logístico Interno CINTAC** es una aplicación web desarrollada con
Django para gestionar cotizaciones de transporte marítimo. Permite a los
usuarios autenticarse, seleccionar una ruta logística, ingresar los datos de
la carga y obtener una cotización en dólares estadounidenses y su conversión
estimada a pesos chilenos.

Esta herramienta automatiza y estandariza las simulaciones de importación marítima de productos metalúrgicos y carga general, calculando con precisión los costos de flete en USD, los tiempos estimados de tránsito y la asignación óptima de contenedores ($20'$ y $40'\text{ HQ}$) en estricto cumplimiento de las normativas viales vigentes en Chile.


---

## ⭐ Características Principales

* **Motor de Cubicaje y Topes Viales:** Asignación automatizada de contenedores considerando los límites normativos chilenos (Decreto Supremo N° 158 MOP): $20\text{ toneladas}$ para contenedores de $20'$ y $25\text{ toneladas}$ para contenedores de $40'\text{ HQ}$.
* **Base de Datos Relacional Centralizada:** Gestión transaccional y estructurada mediante **Neon (PostgreSQL)** y Django ORM, eliminando la dependencia de archivos estáticos dispersos y garantizando la integridad referencial.
* **Autonomía Operativa (Panel CRUD):** Módulo de administración seguro que permite a los usuarios autorizados actualizar tarifas navieras y rutas internacionales en tiempo real sin intervención de desarrollo.
* **Control de Acceso Estricto:** Arquitectura cerrada diseñada bajo el principio de Mínimo Privilegio para un máximo de **3 administradores autorizados** con gestión segura de sesiones.
* **Identidad Visual Corporativa:** Interfaz intuitiva alineada con el manual de marca y paleta institucional de CINTAC (Terracota y Naranja).

---

## Funcionalidades principales

- Inicio y cierre de sesión para usuarios internos.
- Validación de usuarios, correos electrónicos y datos del cliente.
- Selección de puertos de origen y destino.
- Cálculo de contenedores necesarios según el peso de la carga.
- Cálculo de costos fijos, IVA y monto total de la cotización.
- Conversión referencial del total desde USD a CLP.
- Generación de un documento PDF con el detalle de la cotización.
- Consulta del historial de cotizaciones.
- Administración de rutas y tarifas para contenedores 20 HQ y 40 HQ.
- Vista de informe y administración mediante Django.

## 🛠️ Stack Tecnológico

* **Lenguaje Base:** Python 3.10+
* **Framework Web:** Django (Motor lógico, ORM y Django Templates)
* **Base de Datos:** SQLite (Entorno de pruebas local) / **Neon PostgreSQL** (Producción en la nube)
* **Infraestructura & Despliegue:** **Vercel** (CI/CD continuo)
* **Seguridad:** Cifrado de contraseñas PBKDF2-SHA256, protección nativa contra XSS/CSRF (OWASP), protocolos HTTPS/TLS 1.3 y gestión de secretos mediante variables de entorno (`.env`).

## Estructura del proyecto

```text
.
├── Cotizador/                 # Aplicación Django
│   ├── models.py              # Usuarios, rutas, tarifas y cotizaciones
│   ├── forms.py               # Formularios de administración de rutas
│   ├── views.py               # Autenticación, cotización, historial e informes
│   ├── urls.py                # Rutas de la aplicación
│   └── migrations/            # Migraciones de la base de datos
├── ProyectoFinal/
│   ├── settings.py            # Configuración de Django
│   ├── urls.py                # Rutas principales
│   └── static/                # CSS e imágenes
├── templates/                 # Plantillas HTML
├── manage.py                  # Utilidad de administración de Django
└── README.md
```

## Modelo de datos

La aplicación utiliza los siguientes registros principales:

- **Login:** credenciales, correo y rol fijo del usuario interno.
- **ruta_logistica:** puertos de origen y destino, además de días estimados de
  tránsito.
- **tarifa_contenedor:** peso máximo y costo fijo por tipo de contenedor y
  ruta.
- **cotizacion_generada:** cliente, empresa, carga, ruta, usuario, impuestos y
  total calculado.

## Requisitos

- Python 3.10 o superior.
- Una cuenta de **Neon** para crear la base de datos PostgreSQL del despliegue.
- Una cuenta de **Vercel** para publicar la aplicación.
- Git para versionar y desplegar el proyecto.

## Instalación local

1. Clonar el repositorio y acceder a su directorio:

   ```bash
   git clone <URL_DEL_REPOSITORIO>
   cd "Proyecto Final v.3"
   ```

2. Crear y activar un entorno virtual:

   ```bash
   python -m venv .venv
   ```

   En Windows:

   ```powershell
   .venv\Scripts\Activate.ps1
   ```

3. Instalar Django y las dependencias necesarias para PostgreSQL:

   ```bash
   pip install django psycopg[binary] dj-database-url
   ```

4. Ejecutar las migraciones:

   ```bash
   python manage.py migrate
   ```

5. Iniciar el servidor de desarrollo:

   ```bash
   python manage.py runserver
   ```

   La aplicación estará disponible en `http://127.0.0.1:8000/`.

En el entorno local se puede utilizar el archivo `db.sqlite3`. Este archivo
solo sirve para desarrollo; no debe utilizarse como base de datos compartida
en producción.


## ☁️ Arquitectura y Despliegue en la Nube

El sistema está preparado para operar en producción bajo una arquitectura moderna y desacoplada:
1. **Hosting en Vercel:** Despliegue continuo automatizado desde la rama `main`, garantizando tiempos de respuesta mínimos y alta disponibilidad.
2. **Persistencia en Neon (PostgreSQL):** Base de datos relacional *serverless* en la nube con respaldos automáticos e integridad transaccional para la operación simultánea de los administradores de Comercio Exterior.


## Configuración de Neon

Neon aloja la base de datos PostgreSQL utilizada por el entorno desplegado.
Desde el panel de Neon se debe copiar la cadena de conexión y guardarla como
la variable de entorno `DATABASE_URL`. No se debe publicar esta cadena ni
incluirla directamente en el código fuente.

Antes de ejecutar el despliegue, la configuración de Django debe seleccionar
PostgreSQL cuando `DATABASE_URL` esté definida. Luego se deben aplicar las
migraciones contra Neon:

```bash
python manage.py migrate
```

También se recomienda definir en el entorno de producción:

- `SECRET_KEY`: clave secreta de Django.
- `DEBUG=False`: desactiva el modo de depuración.
- `ALLOWED_HOSTS`: dominio asignado por Vercel.
- `DATABASE_URL`: cadena de conexión privada de Neon.

## Despliegue en Vercel

El proyecto contiene `manage.py` y `ProyectoFinal.wsgi`, por lo que Vercel
puede detectar la aplicación Django automáticamente. No se debe subir `.env`
ni usar SQLite como base de datos de producción.

1. En Neon, crea una base PostgreSQL y copia su cadena de conexión.
2. En Vercel, selecciona **Add New Project**, importa este repositorio y deja
   la raíz del proyecto donde está `manage.py`.
3. En **Settings > Environment Variables**, agrega:

   ```text
   DATABASE_URL=<cadena privada de Neon>
   SECRET_KEY=<clave aleatoria nueva>
   DEBUG=False
   ALLOWED_HOSTS=<dominio-personalizado-si-existe>
   CSRF_TRUSTED_ORIGINS=https://<dominio-personalizado-si-existe>
   ```

   Vercel proporciona automáticamente las variables `VERCEL_URL` y
   `VERCEL_PROJECT_PRODUCTION_URL`. La configuración de Django las agrega a
   `ALLOWED_HOSTS` y `CSRF_TRUSTED_ORIGINS`. El dominio de producción
   `cotizador-importacion-cintac-final-alpha.vercel.app` también está incluido
   directamente para evitar que Django rechace la petición mientras el entorno
   no tenga esas variables disponibles.

   Para generar una clave localmente:

   ```powershell
   python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
   ```

4. Ejecuta las migraciones contra Neon desde un entorno local configurado con
   la misma `DATABASE_URL`:

   ```powershell
   python manage.py migrate
   ```

5. Haz **Deploy** en Vercel y comprueba `/`, `/Cotizador/login/` y `/admin/`.
   Los despliegues posteriores se harán automáticamente desde la rama
   configurada.

Vercel sirve la aplicación mediante `ProyectoFinal.wsgi.application`.
`STATIC_ROOT` está configurado para que la colección de archivos estáticos se
realice durante el proceso de despliegue. Si cambias el dominio, actualiza
también `ALLOWED_HOSTS` y `CSRF_TRUSTED_ORIGINS`.

## Rutas principales

| Ruta | Descripción |
| --- | --- |
| `/` | Redirección a la pantalla de inicio de sesión |
| `/Cotizador/login/` | Inicio de sesión |
| `/Cotizador/cotizador/` | Creación de una cotización |
| `/Cotizador/historial/` | Historial de cotizaciones |
| `/Cotizador/informe/` | Informe de cotizaciones |
| `/Cotizador/crear/` | Creación de rutas y tarifas |
| `/Cotizador/editar/` | Edición de rutas y tarifas |
| `/Cotizador/eliminar/` | Eliminación de rutas y tarifas |
| `/admin/` | Administración de Django |

## Seguridad

- Mantener las credenciales de Neon y la clave secreta fuera del repositorio.
- Usar variables de entorno en Vercel.
- Desactivar `DEBUG` en producción.
- Configurar correctamente los dominios permitidos y la protección CSRF antes
  de publicar el sistema.

## 👥 Equipo de Desarrollo

Proyecto desarrollado en el marco del Proyecto Integrado — **INACAP** (Analista Programador / Ingeniería en Ciberseguridad):

* **Christopher Catalán** — [@Multi-Fruit](https://github.com/Multi-Fruit)
* **Michele Barriga** — [@mmich-exe](https://github.com/mmich-exe)
* **Gabriel Silva** — [@gsilva221](https://github.com/gsilva221)