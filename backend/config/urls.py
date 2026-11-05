from django.urls import path

from portal import account_views, auth_views, profile_views, views

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
    path("profile/api/state/", profile_views.profile_state_api, name="profile_state_api"),
    path("profile/api/step/<int:step>/", profile_views.profile_save_step, name="profile_save_step"),
    path("account/api/profile/", account_views.account_profile_api, name="account_profile_api"),
    path("account/api/update/", account_views.account_update_field, name="account_update_field"),
    path("account/api/delete/send-otp/", account_views.account_delete_send_otp, name="account_delete_send_otp"),
    path("account/api/delete/resend-otp/", account_views.account_delete_resend_otp, name="account_delete_resend_otp"),
    path("account/api/delete/verify/", account_views.account_delete_verify, name="account_delete_verify"),
    path("integrations/google/start/", profile_views.google_oauth_start, name="google_oauth_start"),
    path("integrations/google/callback/", profile_views.google_oauth_callback, name="google_oauth_callback"),
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
    path("dashboard/jobs/<uuid:job_id>/delete/", views.delete_job_draft, name="delete_job_draft"),
    path("dashboard/jobs/<uuid:job_id>/draft/", views.get_job_draft, name="get_job_draft"),
]
