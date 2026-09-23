from django.urls import path
from core import views

urlpatterns = [
    path("api/state", views.state),
    path("api/generate", views.generate),
    path("api/publish", views.publish),
    path("api/oncall", views.oncall),
    path("api/coverage", views.coverage),
    path("api/shift", views.shift),
    path("api/team", views.team),
    path("api/person", views.person),
]
