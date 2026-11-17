from .models import Settings


def globals(request):
    if not request.user.is_authenticated:
        return {}
    from .services import late_orders
    return {"gemach_settings": Settings.get(), "late_count": len(late_orders())}
