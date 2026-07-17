class ContentSecurityPolicyMiddleware:
    """ASVS V14: self-only CSP. No third-party scripts/styles/analytics by design."""
    POLICY = ("default-src 'self'; img-src 'self' data:; style-src 'self'; "
              "script-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.headers.setdefault("Content-Security-Policy", self.POLICY)
        response.headers.setdefault("Referrer-Policy", "same-origin")
        return response


class RLSSessionMiddleware:
    """SEC-008 wiring: exposes the authenticated user's PK to Postgres so the RLS
    policies in tracker/0002_rls can enforce. No-op on sqlite and for anonymous users.
    Must sit AFTER AuthenticationMiddleware. Enforcement additionally requires the app
    to connect as a role that does NOT own the tables (see security.md SEC-008)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from django.db import connection
        if connection.vendor == "postgresql" and request.user.is_authenticated:
            with connection.cursor() as cur:
                cur.execute("SELECT set_config('certsleuth.user_id', %s, false)",
                            [str(request.user.pk)])
        response = self.get_response(request)
        if connection.vendor == "postgresql":
            with connection.cursor() as cur:
                cur.execute("SELECT set_config('certsleuth.user_id', '', false)")
        return response
