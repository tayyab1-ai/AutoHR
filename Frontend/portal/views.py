from django.shortcuts import render

from . import data


def landing(request):
    return render(request, "landing.html")


def auth_page(request, mode="signup"):
    context = {
        "mode": mode,
        "is_signup": mode == "signup",
    }
    return render(request, "auth.html", context)


def dashboard(request):
    context = {
        "hr": data.HR_ACCOUNT,
        "kpis": data.KPI_CARDS,
        "funnel": data.PIPELINE_FUNNEL,
        "activity": data.RECENT_ACTIVITY,
        "jobs": data.JOBS,
        "candidates": data.CANDIDATES,
        "interviews": data.INTERVIEWS,
        "kanban": data.KANBAN_COLUMNS,
        "reports": data.REPORTS_SUMMARY,
        "chart_months": data.CHART_MONTHS,
        "chart_values": data.CHART_APPLICATIONS,
        "chart_max": max(data.CHART_APPLICATIONS),
    }
    return render(request, "dashboard.html", context)
