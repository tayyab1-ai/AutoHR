from django.urls import path

from portal import views

urlpatterns = [
    path("", views.landing, name="landing"),
    path("login/", views.auth_page, {"mode": "signin"}, name="login"),
    path("register/", views.auth_page, {"mode": "signup"}, name="register"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("dashboard/jobs/create/", views.create_job_post, name="create_job_post"),
    path(
        "dashboard/jobs/<uuid:job_id>/generate-jd/",
        views.generate_job_jd,
        name="generate_job_jd",
    ),
    path(
        "dashboard/jobs/<uuid:job_id>/prepare-google-form/",
        views.prepare_google_form,
        name="prepare_google_form",
    ),
]
