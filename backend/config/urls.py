from django.conf import settings
from django.conf.urls.static import static
from django.urls import path

from portal import account_views, cv_views, form_views, google_auth_views, profile_views, views

urlpatterns = [
    path("", views.landing, name="landing"),
    path("login/", views.auth_page, {"mode": "signin"}, name="login"),
    path("register/", views.auth_page, {"mode": "signup"}, name="register"),
    path("auth/google/start/", google_auth_views.google_auth_start, name="google_auth_start"),
    path("auth/google/callback/", google_auth_views.google_auth_callback, name="google_auth_callback"),
    path("auth/logout/", google_auth_views.auth_logout_view, name="auth_logout"),
    path("logout/", google_auth_views.auth_logout_get, name="logout"),
    path("profile/api/state/", profile_views.profile_state_api, name="profile_state_api"),
    path("profile/api/step/<int:step>/", profile_views.profile_save_step, name="profile_save_step"),
    path("account/api/profile/", account_views.account_profile_api, name="account_profile_api"),
    path("account/api/integrations/", account_views.account_integrations_api, name="account_integrations_api"),
    path(
        "account/api/integrations/disconnect/",
        account_views.account_disconnect_integration,
        name="account_disconnect_integration",
    ),
    path("account/api/update/", account_views.account_update_field, name="account_update_field"),
    path("account/api/sessions/", account_views.account_sessions_api, name="account_sessions_api"),
    path("account/api/sessions/revoke/", account_views.account_revoke_session, name="account_revoke_session"),
    path("account/api/sessions/revoke-others/", account_views.account_revoke_other_sessions, name="account_revoke_other_sessions"),
    path("account/api/delete/confirm/", account_views.account_delete_confirm, name="account_delete_confirm"),
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
    path(
        "dashboard/jobs/<uuid:job_id>/save-draft-jd/",
        views.save_job_draft_jd,
        name="save_job_draft_jd",
    ),
    path(
        "dashboard/jobs/<uuid:job_id>/form-config/",
        form_views.job_form_config_api,
        name="job_form_config_api",
    ),
    path(
        "dashboard/jobs/<uuid:job_id>/form-config/save/",
        form_views.job_form_config_save,
        name="job_form_config_save",
    ),
    path(
        "dashboard/jobs/<uuid:job_id>/create-google-form/",
        form_views.job_create_google_form,
        name="job_create_google_form",
    ),
    path(
        "dashboard/jobs/<uuid:job_id>/confirm-google-form/",
        form_views.job_confirm_google_form,
        name="job_confirm_google_form",
    ),
    path("dashboard/jobs/<uuid:job_id>/delete/", views.delete_job_draft, name="delete_job_draft"),
    path("dashboard/jobs/<uuid:job_id>/draft/", views.get_job_draft, name="get_job_draft"),
    path(
        "dashboard/jobs/<uuid:job_id>/cv-metrics/",
        cv_views.update_job_cv_metrics_api,
        name="update_job_cv_metrics",
    ),
    path("dashboard/applications/score-cv/", cv_views.score_cv_api, name="score_cv_api"),
    path(
        "dashboard/applications/<uuid:application_id>/decision/",
        cv_views.application_decision_api,
        name="application_decision_api",
    ),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
