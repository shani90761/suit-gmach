from django.shortcuts import redirect

PUBLIC = ("/login/", "/setup/", "/cron/", "/static/", "/healthz")


class LoginRequiredMiddleware:
    """REQ-ROLE-1/2: כל דף דורש כניסה, חוץ ממסך הכניסה."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.user.is_authenticated and not request.path.startswith(PUBLIC):
            from django.contrib.auth import get_user_model
            if not get_user_model().objects.exists():
                return redirect("/setup/")  # התקנה חדשה
            return redirect(f"/login/?next={request.path}")
        return self.get_response(request)
