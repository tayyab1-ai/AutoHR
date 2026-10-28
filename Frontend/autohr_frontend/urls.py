from django.urls import path

from portal import views

urlpatterns = [
    path("", views.landing, name="landing"),
    path("login/", views.auth_page, {"mode": "signin"}, name="login"),
    path("register/", views.auth_page, {"mode": "signup"}, name="register"),
    path("dashboard/", views.dashboard, name="dashboard"),
]
