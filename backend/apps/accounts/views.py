from django.conf import settings
from rest_framework import generics, permissions, status
from rest_framework.authentication import SessionAuthentication
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from .serializers import (
    EmailTokenObtainPairSerializer,
    RegisterSerializer,
    UserSerializer,
)


class LoginView(TokenObtainPairView):
    serializer_class = EmailTokenObtainPairSerializer


class RegisterView(generics.CreateAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = RegisterSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


class MeView(APIView):
    def get(self, request):
        return Response(UserSerializer(request.user).data)


class SessionTokenView(APIView):
    """Émet un JWT à partir d'une session allauth (retour de SSO OIDC/SAML).

    Utilisé après un login social par redirect : le navigateur possède déjà la
    session, on la convertit en JWT pour l'API et le WebSocket.
    """

    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [SessionAuthentication]

    def get(self, request):
        refresh = EmailTokenObtainPairSerializer.get_token(request.user)
        return Response(
            {
                "refresh": str(refresh),
                "access": str(refresh.access_token),
                "user": UserSerializer(request.user).data,
            }
        )


class SsoProvidersView(APIView):
    """Liste les providers SSO (OIDC) configurés, pour le frontend."""

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        from django.urls import reverse

        providers = []
        for app in settings.SOCIALACCOUNT_PROVIDERS.get("openid_connect", {}).get(
            "APPS", []
        ):
            providers.append(
                {
                    "id": app["provider_id"],
                    "name": app.get("name", app["provider_id"]),
                    "login_url": reverse(
                        "openid_connect_login",
                        kwargs={"provider_id": app["provider_id"]},
                    ),
                }
            )
        return Response({"providers": providers})
