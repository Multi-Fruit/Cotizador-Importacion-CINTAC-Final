from django.urls import path
from Cotizador.views import Cotizador, historial, login, logout, informe, crear, editar

urlpatterns = [
    path('login/', login, name='login'),
    path('logout/', logout, name='logout'),
    path('cotizador/', Cotizador, name='cotizador'),
    path('historial/', historial, name='historial'),
    path('informe/', informe, name='informe'),
    path('crear/', crear, name='crear'),
    path('editar/', editar, name='editar'),
    path('editar/<int:ruta_id>/', editar, name='editar'),
]