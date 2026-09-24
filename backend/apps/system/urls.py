from django.urls import path

from .views import GenerateCertView, SystemConfigView, TestLdapView

urlpatterns = [
    path("config/", SystemConfigView.as_view(), name="system-config"),
    path("config/generate-cert/", GenerateCertView.as_view(), name="system-generate-cert"),
    path("config/test-ldap/", TestLdapView.as_view(), name="system-test-ldap"),
]