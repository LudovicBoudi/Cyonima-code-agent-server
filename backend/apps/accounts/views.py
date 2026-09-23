from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import generics, permissions, status, viewsets
from rest_framework.authentication import SessionAuthentication
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from .serializers import (
    AdminUserSerializer,
    CreateUserSerializer,
    EmailTokenObtainPairSerializer,
    RegisterSerializer,
    UserSerializer,
)

User = get_user_model()


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


class AdminUsersViewSet(viewsets.ModelViewSet):
    """Gestion des utilisateurs dans l'appli (réservée aux staff)."""

    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    queryset = User.objects.all().order_by("-date_joined")
    lookup_field = "pk"

    def get_permissions(self):
        return [permissions.IsAdminUser()]

    def get_serializer_class(self):
        if self.action == "create":
            return CreateUserSerializer
        return AdminUserSerializer

    def perform_create(self, serializer):
        serializer.save()

    def perform_destroy(self, instance):
        if instance == self.request.user:
            self.permission_denied(
                self.request, "Vous ne pouvez pas supprimer votre propre compte."
            )
        instance.delete()

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        password = serializer.validated_data.pop("password", None)
        if password:
            try:
                validate_password(password, instance)
            except DjangoValidationError as exc:
                return Response(
                    {"password": list(exc.messages)},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            instance.set_password(password)
        self.perform_update(serializer)
        if getattr(instance, "_prefetched_objects_cache", None):
            instance._prefetched_objects_cache = {}
        return Response(AdminUserSerializer(instance).data)
