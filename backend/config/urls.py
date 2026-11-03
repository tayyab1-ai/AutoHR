from django.urls import path

from portal import auth_views, views

urlpatterns = [
    path("", views.landing, name="landing"),
    path("login/", views.auth_page, {"mode": "signin"}, name="login"),
    path("register/", views.auth_page, {"mode": "signup"}, name="register"),
    path("auth/signup/send-otp/", auth_views.signup_send_otp, name="signup_send_otp"),
    path("auth/signup/verify-otp/", auth_views.signup_verify_otp, name="signup_verify_otp"),
    path("auth/signup/resend-otp/", auth_views.signup_resend_otp, name="signup_resend_otp"),
    path("auth/password/send-otp/", auth_views.password_reset_send_otp, name="password_reset_send_otp"),
    path("auth/password/verify-otp/", auth_views.password_reset_verify_otp, name="password_reset_verify_otp"),
    path("auth/password/resend-otp/", auth_views.password_reset_resend_otp, name="password_reset_resend_otp"),
    path("auth/login/", auth_views.auth_login, name="auth_login"),
    path("auth/logout/", auth_views.auth_logout_view, name="auth_logout"),
    path("logout/", auth_views.auth_logout_get, name="logout"),
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
