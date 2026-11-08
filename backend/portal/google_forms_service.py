"""Create Google Forms for candidate applications."""

import json
import logging

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .form_catalog import field_by_key
from .google_oauth import get_credentials

_logger = logging.getLogger(__name__)

DROPDOWN_OPTIONS: dict[str, list[str]] = {
    "education_level": ["Matric / O-Level", "Intermediate / A-Level", "Bachelor's", "Master's", "PhD", "Other"],
    "employment_status": ["Employed", "Unemployed", "Freelancing", "Student", "Self-employed"],
    "notice_period": ["Immediate", "1 week", "2 weeks", "1 month", "2 months", "3+ months"],
}


def _choice_options(field: dict) -> list[str]:
    key = field.get("key") or ""
    if key in DROPDOWN_OPTIONS:
        return DROPDOWN_OPTIONS[key]
    return ["Option 1", "Option 2", "Other"]


def _create_item_request(field: dict, index: int) -> dict:
    title = field["label"]
    ftype = field["type"]
    required = bool(field.get("required"))

    question: dict = {"required": required}
    if ftype == "date":
        question["dateQuestion"] = {"includeTime": False, "includeYear": True}
    elif ftype == "yes_no":
        question["choiceQuestion"] = {
            "type": "RADIO",
            "options": [{"value": "Yes"}, {"value": "No"}],
        }
    elif ftype == "dropdown":
        opts = _choice_options(field)
        question["choiceQuestion"] = {
            "type": "DROP_DOWN",
            "options": [{"value": v} for v in opts],
        }
    elif ftype == "checkbox_required":
        question["choiceQuestion"] = {
            "type": "RADIO",
            "options": [{"value": "I agree"}],
        }
        question["required"] = True
    elif ftype in ("paragraph", "checkboxes"):
        question["textQuestion"] = {"paragraph": True}
    else:
        question["textQuestion"] = {"paragraph": False}

    return {
        "createItem": {
            "item": {
                "title": title,
                "questionItem": {"question": question},
            },
            "location": {"index": index},
        }
    }


def create_candidate_application_form(
    user_id,
    *,
    title: str,
    description: str,
    selected_field_keys: list[str],
) -> tuple[str, str, str]:
    """
    Returns (form_id, responder_url, editor_url).
    """
    creds = get_credentials(user_id, "google_workspace")
    if not creds or not creds.token:
        raise RuntimeError(
            "Google Workspace is not connected or the token expired. Open Profile → step 3 and connect Google again."
        )

    try:
        service = build("forms", "v1", credentials=creds, cache_discovery=False)
        # Forms API: on create(), only info.title is allowed; everything else uses batchUpdate.
        created = service.forms().create(body={"info": {"title": title[:300]}}).execute()
        form_id = created["formId"]

        requests: list[dict] = []
        if description:
            requests.append(
                {
                    "updateFormInfo": {
                        "info": {"description": description[:5000]},
                        "updateMask": "description",
                    }
                }
            )

        index = 0
        for key in selected_field_keys:
            field = field_by_key(key)
            if not field:
                continue
            requests.append(_create_item_request(field, index))
            index += 1

        chunk = 12
        for offset in range(0, len(requests), chunk):
            batch = requests[offset : offset + chunk]
            service.forms().batchUpdate(formId=form_id, body={"requests": batch}).execute()

        responder_url = f"https://docs.google.com/forms/d/{form_id}/viewform"
        editor_url = f"https://docs.google.com/forms/d/{form_id}/edit"
        return form_id, responder_url, editor_url
    except HttpError as exc:
        msg = str(exc)
        if exc.content:
            try:
                payload = json.loads(exc.content.decode("utf-8"))
                msg = payload.get("error", {}).get("message") or msg
            except Exception:
                pass
        _logger.warning("Google Forms API error: %s", msg)
        if "Only info.title can be set when creating" in msg:
            raise RuntimeError(msg) from exc
        raise RuntimeError(
            f"{msg} Enable the Google Forms API in Google Cloud Console if needed, then reconnect Google under Account → Integrations."
        ) from exc
