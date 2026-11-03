from datetime import date

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from .choices import (
    DEPARTMENTS,
    EDUCATION_LEVELS,
    EMPLOYMENT_TYPES,
    JOB_CATEGORIES,
    JOB_POST_TONES,
    PAKISTAN_CITIES,
    SALARY_PERIODS,
    TECH_JOB_CATEGORIES,
    URGENCY_LEVELS,
    WORK_MODES,
)


def _split_tags(value: str) -> list[str]:
    if not value or not str(value).strip():
        return []
    return [part.strip() for part in str(value).split(",") if part.strip()]


class JobIntakeForm(forms.Form):
    title = forms.CharField(max_length=200, label="Job Title")
    department = forms.ChoiceField(choices=DEPARTMENTS, label="Department")
    job_category = forms.ChoiceField(choices=JOB_CATEGORIES, label="Job Category")
    employment_type = forms.ChoiceField(choices=EMPLOYMENT_TYPES, label="Employment Type")
    work_mode = forms.ChoiceField(choices=WORK_MODES, label="Work Mode")
    urgency_level = forms.ChoiceField(choices=URGENCY_LEVELS, label="Urgency Level")
    city = forms.ChoiceField(choices=PAKISTAN_CITIES, label="Job Location — City")
    target_hires = forms.IntegerField(min_value=1, max_value=500, label="Number of Vacancies")
    job_description = forms.CharField(widget=forms.Textarea(attrs={"rows": 5}), label="Job Description")
    company_name = forms.CharField(max_length=200, label="Company Name")
    posting_date = forms.DateField(label="Job Posting Date")
    application_deadline = forms.DateField(label="Application Deadline")

    min_experience_years = forms.IntegerField(min_value=0, max_value=60, label="Minimum Experience (Years)")
    max_experience_years = forms.IntegerField(required=False, min_value=0, max_value=60, label="Maximum Experience (Years)")
    fresh_graduate_eligible = forms.ChoiceField(
        choices=[("yes", "Yes"), ("no", "No")],
        label="Is Fresh Graduate Eligible?",
    )
    min_education_level = forms.ChoiceField(choices=EDUCATION_LEVELS, label="Minimum Education Level")

    required_skills_csv = forms.CharField(required=False, widget=forms.HiddenInput)
    programming_languages_csv = forms.CharField(required=False, widget=forms.HiddenInput)
    frameworks_csv = forms.CharField(required=False, widget=forms.HiddenInput)
    tools_csv = forms.CharField(required=False, widget=forms.HiddenInput)
    cloud_platforms_csv = forms.CharField(required=False, widget=forms.HiddenInput)
    technical_knowledge = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}), label="Required Technical Knowledge")

    min_salary = forms.DecimalField(required=False, min_value=0, max_digits=12, decimal_places=2, label="Minimum Salary")
    max_salary = forms.DecimalField(required=False, min_value=0, max_digits=12, decimal_places=2, label="Maximum Salary")
    salary_period = forms.ChoiceField(choices=SALARY_PERIODS, label="Salary Period")
    salary_negotiable = forms.BooleanField(required=False, label="Salary Negotiable?")
    performance_bonus = forms.BooleanField(required=False, label="Performance Bonus")
    commission_incentives = forms.BooleanField(required=False, label="Commission / Incentives")
    health_insurance = forms.BooleanField(required=False, label="Health Insurance")
    paid_leave_policy = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}), label="Paid Leave Policy")
    provident_fund = forms.BooleanField(required=False, label="Provident Fund / Retirement Benefits")
    other_benefits = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}), label="Other Benefits")
    relocation_assistance = forms.BooleanField(required=False, label="Relocation Assistance")
    equipment_provided = forms.BooleanField(required=False, label="Equipment Provided")

    job_post_tone = forms.ChoiceField(choices=JOB_POST_TONES, label="Job Post Tone")
    custom_tone_instructions = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
        label="Custom tone instructions",
    )
    shortlist_after_cv_count = forms.IntegerField(min_value=20, max_value=30, initial=25, label="Number of Candidates to Shortlist for Interview")
    shortlist_after_interview_count = forms.IntegerField(
        min_value=1,
        max_value=500,
        initial=10,
        label="Number of Candidates to Shortlist After Interview",
    )

    def __init__(self, *args, company_name: str = "", **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            self.fields["posting_date"].initial = timezone.localdate()
            self.fields["company_name"].initial = company_name
            if company_name:
                self.fields["company_name"].widget.attrs["readonly"] = True
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                continue
            css = "db-input" if not isinstance(field.widget, forms.Select) else "db-select"
            field.widget.attrs.setdefault("class", css)
            if isinstance(field.widget, forms.Textarea):
                field.widget.attrs["class"] = css
            field.widget.attrs.setdefault("style", "width:100%;")

    def clean(self):
        cleaned = super().clean()
        if self.errors:
            return cleaned

        posting = cleaned.get("posting_date")
        deadline = cleaned.get("application_deadline")
        if posting and deadline and deadline < posting:
            self.add_error("application_deadline", "Application deadline cannot be before the posting date.")

        min_exp = cleaned.get("min_experience_years")
        max_exp = cleaned.get("max_experience_years")
        if max_exp is not None and min_exp is not None and max_exp < min_exp:
            self.add_error("max_experience_years", "Maximum experience cannot be less than minimum experience.")

        min_sal = cleaned.get("min_salary")
        max_sal = cleaned.get("max_salary")
        if min_sal is not None and max_sal is not None and max_sal < min_sal:
            self.add_error("max_salary", "Maximum salary cannot be less than minimum salary.")

        company_name = cleaned.get("company_name", "").strip()
        expected = getattr(self, "expected_company_name", "")
        if expected and company_name.lower() != expected.lower():
            self.add_error("company_name", "Company name must match your registered company.")

        required_skills = _split_tags(cleaned.get("required_skills_csv", ""))
        if not required_skills:
            self.add_error("required_skills_csv", "Add at least one required skill.")

        category = cleaned.get("job_category")
        programming = _split_tags(cleaned.get("programming_languages_csv", ""))
        if category in TECH_JOB_CATEGORIES and not programming:
            self.add_error(
                "programming_languages_csv",
                "Required programming languages are needed for this job category.",
            )

        tone = cleaned.get("job_post_tone")
        custom = (cleaned.get("custom_tone_instructions") or "").strip()
        if tone == "custom" and not custom:
            self.add_error("custom_tone_instructions", "Describe the custom writing style you want.")

        key_items = [v.strip() for v in self.data.getlist("key_responsibilities") if v.strip()]
        if not key_items:
            self.add_error(None, "Add at least one key responsibility.")

        cleaned["required_skills_list"] = required_skills
        cleaned["programming_languages_list"] = programming
        cleaned["frameworks_list"] = _split_tags(cleaned.get("frameworks_csv", ""))
        cleaned["tools_list"] = _split_tags(cleaned.get("tools_csv", ""))
        cleaned["cloud_platforms_list"] = _split_tags(cleaned.get("cloud_platforms_csv", ""))
        cleaned["key_responsibilities_list"] = key_items
        cleaned["daily_tasks_list"] = [v.strip() for v in self.data.getlist("daily_tasks") if v.strip()]
        cleaned["fresh_graduate_eligible_bool"] = cleaned.get("fresh_graduate_eligible") == "yes"
        return cleaned
