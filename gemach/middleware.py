from django.shortcuts import redirect

PUBLIC = ("/login/", "/cron/", "/static/", "/healthz")


class LoginRequiredMiddleware:
    """REQ-ROLE-1/2: כל דף דורש כניסה, חוץ ממסך הכניסה."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.user.is_authenticated and not request.path.startswith(PUBLIC):
            return redirect(f"/login/?next={request.path}")
        return self.get_response(request)
