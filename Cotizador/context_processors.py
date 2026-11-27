from .models import Login


def usuario_conectado(request):
    login_id = request.session.get('login_id')
    if login_id is None:
        return {}
    nombre = Login.objects.filter(pk=login_id).values_list('username', flat=True).first()
    return {'usuario_conectado': nombre}
