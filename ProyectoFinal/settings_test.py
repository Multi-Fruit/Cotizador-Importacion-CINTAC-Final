"""Configuración exclusiva de pruebas: jamás abre db.sqlite3 ni DATABASE_URL."""
from pathlib import Path
from tempfile import TemporaryDirectory
from .settings import *  # noqa: F403

SECRET_KEY = 'e2e-only-not-a-production-secret'
# Archivo temporal para que live_server use una conexión por hilo. SQLite en
# memoria hace compartir una conexión única y no sirve para P20 concurrente.
_test_directory = TemporaryDirectory(prefix='cintac-tests-')
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': Path(_test_directory.name) / 'unused.sqlite3',
        'TEST': {'NAME': Path(_test_directory.name) / 'test.sqlite3'},
    },
}
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
ALLOWED_HOSTS = ['localhost', '127.0.0.1', 'testserver']