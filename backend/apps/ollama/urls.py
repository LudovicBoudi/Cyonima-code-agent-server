from django.urls import path

from .views import OllamaModelDetailView, OllamaModelsView, OllamaPullView

urlpatterns = [
    path("models/", OllamaModelsView.as_view(), name="ollama-models"),
    path("models/<str:name>/pull/", OllamaPullView.as_view(), name="ollama-pull"),
    path("models/<str:name>/", OllamaModelDetailView.as_view(), name="ollama-model-detail"),
]
