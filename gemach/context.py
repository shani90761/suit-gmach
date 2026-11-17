from .models import Settings


def globals(request):
    if not request.user.is_authenticated:
        return {}
    return {"gemach_settings": Settings.get()}
