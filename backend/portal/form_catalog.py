"""Standard candidate application form sections and fields (Google Forms mapping)."""

FORM_SECTIONS = [
    {
        "id": "personal",
        "title": "Personal Information",
        "fields": [
            {"key": "full_name", "label": "Full Name", "type": "short_text", "required": True, "default_on": True},
            {"key": "email", "label": "Email Address", "type": "short_text", "required": True, "default_on": True},
            {"key": "phone", "label": "Phone Number", "type": "short_text", "required": True, "default_on": True},
            {"key": "current_city", "label": "Current City", "type": "short_text", "required": True, "default_on": True},
            {"key": "country", "label": "Country", "type": "short_text", "required": True, "default_on": True},
            {"key": "linkedin", "label": "LinkedIn Profile", "type": "short_text", "required": False, "default_on": True},
            {"key": "github", "label": "GitHub Profile", "type": "short_text", "required": False, "default_on": True},
            {"key": "portfolio", "label": "Portfolio / Personal Website", "type": "short_text", "required": False, "default_on": True},
        ],
    },
    {
        "id": "education",
        "title": "Education",
        "fields": [
            {"key": "education_level", "label": "Highest Education Level", "type": "dropdown", "required": True, "default_on": True},
            {"key": "degree", "label": "Degree / Qualification", "type": "short_text", "required": True, "default_on": True},
            {"key": "field_of_study", "label": "Field of Study", "type": "short_text", "required": True, "default_on": True},
            {"key": "university", "label": "University / Institute", "type": "short_text", "required": True, "default_on": True},
            {"key": "graduation_year", "label": "Graduation Year", "type": "number", "required": True, "default_on": True},
            {"key": "currently_studying", "label": "Currently Studying?", "type": "yes_no", "required": False, "default_on": True},
        ],
    },
    {
        "id": "experience",
        "title": "Professional Experience",
        "fields": [
            {"key": "total_experience_years", "label": "Total Professional Experience (Years)", "type": "number", "required": True, "default_on": True},
            {"key": "relevant_experience_years", "label": "Relevant Experience (Years)", "type": "number", "required": True, "default_on": True},
            {"key": "employment_status", "label": "Current Employment Status", "type": "dropdown", "required": True, "default_on": True},
            {"key": "current_company", "label": "Current Company", "type": "short_text", "required": False, "default_on": True},
            {"key": "current_job_title", "label": "Current Job Title", "type": "short_text", "required": False, "default_on": True},
            {"key": "previous_company", "label": "Previous Company", "type": "short_text", "required": False, "default_on": False},
            {"key": "previous_job_title", "label": "Previous Job Title", "type": "short_text", "required": False, "default_on": False},
            {"key": "notice_period", "label": "Notice Period", "type": "dropdown", "required": False, "default_on": True},
            {"key": "expected_salary", "label": "Expected Salary (PKR)", "type": "short_text", "required": True, "default_on": True},
            {"key": "available_to_join", "label": "Available to Join", "type": "date", "required": False, "default_on": True},
        ],
    },
    {
        "id": "technical",
        "title": "Technical Skills and Expertise",
        "fields": [
            {"key": "primary_skills", "label": "Primary Technical Skills", "type": "paragraph", "required": True, "default_on": True},
            {"key": "programming_languages", "label": "Programming Languages", "type": "checkboxes", "required": True, "default_on": True},
            {"key": "frameworks", "label": "Frameworks and Libraries", "type": "paragraph", "required": False, "default_on": True},
            {"key": "tools", "label": "Tools and Technologies", "type": "paragraph", "required": False, "default_on": True},
            {"key": "certifications", "label": "Relevant Certifications", "type": "paragraph", "required": False, "default_on": False},
            {"key": "job_technologies", "label": "Experience with Required Job Technologies", "type": "paragraph", "required": True, "default_on": True},
        ],
    },
    {
        "id": "projects",
        "title": "Projects and Practical Experience",
        "fields": [
            {"key": "has_projects", "label": "Have you worked on professional or personal projects?", "type": "yes_no", "required": True, "default_on": True},
            {"key": "recent_project_name", "label": "Most Recent / Relevant Project Name", "type": "short_text", "required": True, "default_on": True},
            {"key": "project_description", "label": "Explain the most relevant project you completed recently", "type": "paragraph", "required": True, "default_on": True},
            {"key": "project_role", "label": "What was your role in this project?", "type": "paragraph", "required": True, "default_on": True},
            {"key": "project_technologies", "label": "Which technologies and tools did you use?", "type": "paragraph", "required": True, "default_on": True},
            {"key": "project_problem", "label": "What problem did the project solve?", "type": "paragraph", "required": True, "default_on": True},
            {"key": "project_challenges", "label": "What challenges did you face, and how did you solve them?", "type": "paragraph", "required": True, "default_on": True},
            {"key": "project_outcome", "label": "What was the outcome or impact of the project?", "type": "paragraph", "required": True, "default_on": True},
            {"key": "project_link", "label": "Project GitHub / Live Demo Link", "type": "short_text", "required": False, "default_on": True},
        ],
    },
    {
        "id": "job_specific",
        "title": "Job-Specific Questions and Confirmation",
        "fields": [
            {"key": "why_interested", "label": "Why are you interested in this position?", "type": "paragraph", "required": True, "default_on": True},
            {"key": "why_suitable", "label": "Why do you think you are a suitable candidate?", "type": "paragraph", "required": True, "default_on": True},
            {"key": "what_different", "label": "What makes you different from other applicants?", "type": "paragraph", "required": True, "default_on": True},
            {"key": "comfortable_requirements", "label": "Are you comfortable with the job requirements?", "type": "yes_no", "required": True, "default_on": True},
            {"key": "when_can_join", "label": "When can you join?", "type": "date", "required": False, "default_on": True},
            {"key": "anything_else", "label": "Anything else you want us to know?", "type": "paragraph", "required": False, "default_on": True},
            {"key": "declaration_accuracy", "label": "I declare that the information provided is accurate", "type": "checkbox_required", "required": True, "default_on": True},
        ],
    },
]


def default_selected_field_keys() -> list[str]:
    keys = []
    for section in FORM_SECTIONS:
        for field in section["fields"]:
            if field.get("default_on"):
                keys.append(field["key"])
    return keys


def field_by_key(key: str) -> dict | None:
    for section in FORM_SECTIONS:
        for field in section["fields"]:
            if field["key"] == key:
                return {**field, "section_id": section["id"], "section_title": section["title"]}
    return None


def catalog_for_api() -> list[dict]:
    return FORM_SECTIONS
