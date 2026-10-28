"""
Static demo data for the AutoHR frontend-only preview.

Everything here is placeholder content localized for a Pakistani HR
audience: PKR salaries, Lahore/Karachi/Islamabad/Rawalpindi/Faisalabad
offices, +92 phone numbers, and Rozee.pk / Indeed Pakistan as the job
boards. None of this is persisted anywhere yet -- it only exists so the
templates have something realistic to render.
"""

HR_ACCOUNT = {
    "full_name": "Ayesha Khan",
    "job_title": "HR Manager",
    "email": "ayesha.khan@northbridge.pk",
    "phone": "+92 300 1234567",
    "company_name": "Northbridge Technologies",
    "company_website": "https://northbridge.pk",
    "industry": "Software & IT Services",
    "company_size": "51-200",
    "country": "Pakistan",
    "city": "Lahore",
    "office_address": "3rd Floor, Liberty Tower, Gulberg III",
    "linkedin_profile_url": "https://www.linkedin.com/company/northbridge-technologies",
    "linkedin_email": "careers.linkedin@northbridge.pk",
    "indeed_email": "careers.indeed@northbridge.pk",
    "rozee_email": "careers.rozee@northbridge.pk",
    "initials": "AK",
}

KPI_CARDS = [
    {
        "label": "Active Job Postings",
        "value": "18",
        "trend": "+3 this month",
        "icon": "bi-briefcase-fill",
        "tone": "gold",
        "hint": "Roles currently live on the AutoHR careers page, Rozee.pk, and Indeed Pakistan.",
    },
    {
        "label": "Applications Received",
        "value": "1,284",
        "trend": "+212 this week",
        "icon": "bi-people-fill",
        "tone": "green",
        "hint": "Total inbound applications across all channels for the last 30 days.",
    },
    {
        "label": "AI Shortlisted",
        "value": "96",
        "trend": "Top 7.5% of pool",
        "icon": "bi-stars",
        "tone": "purple",
        "hint": "Candidates the CV screening model ranked above the shortlist threshold.",
    },
    {
        "label": "Interviews Scheduled",
        "value": "42",
        "trend": "18 this week",
        "icon": "bi-camera-video-fill",
        "tone": "teal",
        "hint": "3-stage AI video interviews booked through the candidate scheduling link.",
    },
]

PIPELINE_FUNNEL = [
    {"stage": "Posted", "count": 1284, "pct": 100, "css": "post"},
    {"stage": "Screened", "count": 540, "pct": 72, "css": "screen"},
    {"stage": "Interviewed", "count": 96, "pct": 38, "css": "interview"},
    {"stage": "Decided", "count": 24, "pct": 14, "css": "decide"},
]

RECENT_ACTIVITY = [
    {
        "icon": "bi-inbox-fill",
        "tone": "gold",
        "text": "New application received for <strong>Senior Full Stack Engineer</strong> from Hamza Siddiqui",
        "meta": "4m ago · via Rozee.pk",
    },
    {
        "icon": "bi-star-fill",
        "tone": "green",
        "text": "<strong>Fatima Noor</strong> shortlisted for Product Manager · AI Score 93%",
        "meta": "22m ago · AI Screening",
    },
    {
        "icon": "bi-calendar-check-fill",
        "tone": "purple",
        "text": "Interview scheduled with <strong>Bilal Hussain</strong> for UI/UX Designer",
        "meta": "1h ago · 3-Stage AI Video",
    },
    {
        "icon": "bi-check-circle-fill",
        "tone": "teal",
        "text": "Offer accepted by <strong>Sana Malik</strong> for Data Analyst",
        "meta": "3h ago · Phase 4 Completed",
    },
    {
        "icon": "bi-envelope-fill",
        "tone": "gold",
        "text": "Rejection email auto-sent to 14 unshortlisted candidates for DevOps Engineer",
        "meta": "5h ago · Automated Mailer",
    },
]

JOBS = [
    {
        "title": "Senior Full Stack Engineer",
        "department": "Engineering",
        "city": "Lahore",
        "salary": "PKR 250,000 – 400,000 / month",
        "hires": 2,
        "applicants": 214,
        "status": "live",
        "boards": ["Rozee.pk", "Indeed PK"],
        "posted": "12 Oct 2026",
    },
    {
        "title": "Product Manager",
        "department": "Product",
        "city": "Karachi",
        "salary": "PKR 300,000 – 450,000 / month",
        "hires": 1,
        "applicants": 158,
        "status": "live",
        "boards": ["Rozee.pk", "LinkedIn"],
        "posted": "08 Oct 2026",
    },
    {
        "title": "UI/UX Designer",
        "department": "Design",
        "city": "Islamabad",
        "salary": "PKR 150,000 – 220,000 / month",
        "hires": 1,
        "applicants": 121,
        "status": "live",
        "boards": ["Rozee.pk", "Indeed PK"],
        "posted": "05 Oct 2026",
    },
    {
        "title": "Data Analyst",
        "department": "Analytics",
        "city": "Lahore",
        "salary": "PKR 120,000 – 180,000 / month",
        "hires": 2,
        "applicants": 176,
        "status": "draft",
        "boards": ["Rozee.pk"],
        "posted": "Not yet posted",
    },
    {
        "title": "DevOps Engineer",
        "department": "Engineering",
        "city": "Karachi",
        "salary": "PKR 200,000 – 320,000 / month",
        "hires": 1,
        "applicants": 97,
        "status": "closed",
        "boards": ["Rozee.pk", "Indeed PK"],
        "posted": "18 Sep 2026",
    },
    {
        "title": "HR Business Partner",
        "department": "People",
        "city": "Rawalpindi",
        "salary": "PKR 180,000 – 260,000 / month",
        "hires": 1,
        "applicants": 64,
        "status": "live",
        "boards": ["Rozee.pk"],
        "posted": "20 Oct 2026",
    },
]

CANDIDATES = [
    {
        "id": 1,
        "name": "Hamza Siddiqui",
        "initials": "HS",
        "role": "Senior Full Stack Engineer",
        "city": "Lahore",
        "score": 93,
        "skills_score": 95,
        "exp_score": 90,
        "status": "shortlisted",
        "applied": "4m ago",
        "experience": "Senior Software Engineer at Systems Limited (2020–Present). Led a team of 5 building a core banking platform serving 2M+ customers.",
        "education": "BS Computer Science — LUMS, 2019",
        "skills": ["React", "Node.js", "PostgreSQL", "AWS", "Docker"],
        "insight": "Strong product-engineering track record with direct experience on fintech-scale systems. Matches 5 of 5 required skills.",
    },
    {
        "id": 2,
        "name": "Fatima Noor",
        "initials": "FN",
        "role": "Product Manager",
        "city": "Karachi",
        "score": 91,
        "skills_score": 89,
        "exp_score": 93,
        "status": "shortlisted",
        "applied": "22m ago",
        "experience": "Product Manager at Folio3 (2019–Present). Shipped 3 B2B SaaS products from zero to revenue across the GCC and Pakistan.",
        "education": "MBA — IBA Karachi, 2018",
        "skills": ["Roadmapping", "Stakeholder Management", "SQL", "Figma"],
        "insight": "Clear ownership of full product lifecycle with measurable business outcomes. Strong communication in writing sample.",
    },
    {
        "id": 3,
        "name": "Bilal Hussain",
        "initials": "BH",
        "role": "UI/UX Designer",
        "city": "Islamabad",
        "score": 88,
        "skills_score": 92,
        "exp_score": 81,
        "status": "interviewing",
        "applied": "1h ago",
        "experience": "Product Designer at 10Pearls (2021–Present). Redesigned the core mobile app, improving onboarding completion by 34%.",
        "education": "BS Visual Design — NCA Lahore, 2020",
        "skills": ["Figma", "Design Systems", "Prototyping", "User Research"],
        "insight": "Portfolio shows strong systems thinking. Interview will probe collaboration with engineering teams.",
    },
    {
        "id": 4,
        "name": "Sana Malik",
        "initials": "SM",
        "role": "Data Analyst",
        "city": "Lahore",
        "score": 85,
        "skills_score": 84,
        "exp_score": 86,
        "status": "shortlisted",
        "applied": "3h ago",
        "experience": "Data Analyst at Netsol Technologies (2021–Present). Built dashboards used by 40+ regional sales managers.",
        "education": "BS Statistics — Punjab University, 2021",
        "skills": ["SQL", "Power BI", "Python", "Excel"],
        "insight": "Solid analytical fundamentals, slightly light on Python depth relative to senior requirement.",
    },
    {
        "id": 5,
        "name": "Usman Tariq",
        "initials": "UT",
        "role": "DevOps Engineer",
        "city": "Faisalabad",
        "score": 79,
        "skills_score": 77,
        "exp_score": 81,
        "status": "rejected",
        "applied": "5h ago",
        "experience": "Systems Administrator at a regional textile ERP vendor (2018–Present). Limited exposure to container orchestration at scale.",
        "education": "BS Information Technology — GCUF, 2017",
        "skills": ["Linux", "Bash", "Jenkins"],
        "insight": "Below the Kubernetes and Terraform threshold required for this role; archived for future mid-level openings.",
    },
    {
        "id": 6,
        "name": "Hira Shahzad",
        "initials": "HS",
        "role": "HR Business Partner",
        "city": "Rawalpindi",
        "score": 90,
        "skills_score": 88,
        "exp_score": 92,
        "status": "shortlisted",
        "applied": "6h ago",
        "experience": "HR Generalist at a Rawalpindi-based manufacturing group (2019–Present). Ran full-cycle recruitment for 120+ hires per year.",
        "education": "BBA Human Resources — FAST-NU, 2018",
        "skills": ["Recruitment", "Employee Relations", "HRIS", "Labour Law"],
        "insight": "Deep local hiring experience and labour-law fluency relevant to the Punjab offices.",
    },
]

INTERVIEWS = [
    {
        "candidate": "Bilal Hussain",
        "role": "UI/UX Designer",
        "stage": "Technical",
        "date": "27 Oct 2026",
        "time": "11:00 AM PKT",
        "status": "scheduled",
    },
    {
        "candidate": "Hamza Siddiqui",
        "role": "Senior Full Stack Engineer",
        "stage": "Screening",
        "date": "27 Oct 2026",
        "time": "2:30 PM PKT",
        "status": "scheduled",
    },
    {
        "candidate": "Fatima Noor",
        "role": "Product Manager",
        "stage": "Behavioral",
        "date": "28 Oct 2026",
        "time": "10:00 AM PKT",
        "status": "scheduled",
    },
    {
        "candidate": "Mehak Fatima",
        "role": "QA Engineer",
        "stage": "Technical",
        "date": "25 Oct 2026",
        "time": "4:00 PM PKT",
        "status": "completed",
    },
    {
        "candidate": "Ali Hamza",
        "role": "DevOps Engineer",
        "stage": "Screening",
        "date": "23 Oct 2026",
        "time": "1:00 PM PKT",
        "status": "completed",
    },
]

KANBAN_COLUMNS = [
    {
        "title": "Applied",
        "count": 214,
        "candidates": [
            {"name": "Zainab Qureshi", "role": "Full Stack Engineer", "score": 71},
            {"name": "Kamran Akhtar", "role": "Full Stack Engineer", "score": 64},
            {"name": "Noor ul Ain", "role": "Full Stack Engineer", "score": 58},
        ],
    },
    {
        "title": "AI Screened",
        "count": 96,
        "candidates": [
            {"name": "Hamza Siddiqui", "role": "Full Stack Engineer", "score": 93},
            {"name": "Sana Malik", "role": "Data Analyst", "score": 85},
        ],
    },
    {
        "title": "Interviewing",
        "count": 42,
        "candidates": [
            {"name": "Bilal Hussain", "role": "UI/UX Designer", "score": 88},
            {"name": "Fatima Noor", "role": "Product Manager", "score": 91},
        ],
    },
    {
        "title": "Decided",
        "count": 24,
        "candidates": [
            {"name": "Hira Shahzad", "role": "HR Business Partner", "score": 90},
            {"name": "Sana Malik", "role": "Data Analyst", "score": 85},
        ],
    },
]

REPORTS_SUMMARY = {
    "time_to_hire": "21 days",
    "cost_per_hire": "PKR 38,500",
    "offer_acceptance": "86%",
    "top_source": "Rozee.pk (58% of hires)",
}

CHART_MONTHS = ["May", "Jun", "Jul", "Aug", "Sep", "Oct"]
CHART_APPLICATIONS = [640, 810, 760, 980, 1120, 1284]
