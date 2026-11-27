from django.urls import path
from Cotizador.views import Cotizador, detalle_cotizacion, eliminar, historial, login, logout, informe, crear, editar

urlpatterns = [
    path('login/', login, name='login'),
    path('logout/', logout, name='logout'),
    path('cotizador/', Cotizador, name='cotizador'),
    path('historial/', historial, name='historial'),
    path('informe/', informe, name='informe'),
    path('historial/<int:cotizacion_id>/detalle/', detalle_cotizacion, name='detalle_cotizacion'),
    path('crear/', crear, name='crear'),
    path('editar/', editar, name='editar'),
    path('editar/<int:ruta_id>/', editar, name='editar'),
    path('eliminar/', eliminar, name='eliminar'),
]