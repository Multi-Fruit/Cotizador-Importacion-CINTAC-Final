from django.urls import path
from Cotizador.views import Cotizador, historial, login, logout

urlpatterns = [
    path('login/', login, name='login'),
    path('logout/', logout, name='logout'),
    path('cotizador/', Cotizador, name='cotizador'),
    path('historial/', historial, name='historial'),
]