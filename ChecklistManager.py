# ChecklistManager.py
import os
import json
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("API_KEY")


class ChecklistManager:
    """
    Manages the daily Paramedic Checklist - tracks items in any order,
    detects which item user is reporting on, and maintains completion status.
    """

    CHECKLIST_ITEMS = {
        "ACRc": {
            "type": "ACR Completion",
            "description": "Number of ACRs/PCRs that are unfinished",
            "guideline": "Complete within 24 hours of call",
            "keywords": ["acr", "pcr", "ambulance call report", "patient care report", "unfinished reports"]
        },
        "ACEr": {
            "type": "ACE Response",
            "description": "Number of ACE reviews requiring comment",
            "guideline": "Complete within 1 week of BH review",
            "keywords": ["ace", "review", "comment", "base hospital"]
        },
        "CERT-DL": {
            "type": "Drivers License",
            "description": "Drivers License Validity",
            "guideline": "Valid license required",
            "keywords": ["driver", "license", "dl", "driving"]
        },
        "CERT-Va": {
            "type": "Vaccinations",
            "description": "Required vaccinations up to date",
            "guideline": "Per vaccination guidelines",
            "keywords": ["vaccination", "vaccine", "shots", "immunization", "flu shot"]
        },
        "CERT-CE": {
            "type": "Education",
            "description": "Continuous Education Status",
            "guideline": "CME requirements met",
            "keywords": ["education", "cme", "training", "certification", "continuing education"]
        },
        "UNIF": {
            "type": "Uniform",
            "description": "Uniform credits available",
            "guideline": "Uniform order credits available",
            "keywords": ["uniform", "clothes", "gear", "credits"]
        },
        "CRIM": {
            "type": "CRC",
            "description": "Criminal Record Check",
            "guideline": "Criminal Issue Free",
            "keywords": ["criminal", "crc", "record check", "background"]
        },
        "ACP": {
            "type": "ACP Status",
            "description": "Advanced Care Paramedic certification valid",
            "guideline": "ACP certification current",
            "keywords": ["acp", "advanced care", "cert", "certification"]
        },
        "VAC": {
            "type": "Vacation",
            "description": "Vacation requested and approved",
            "guideline": "Yearly vacation approved",
            "keywords": ["vacation", "time off", "holiday", "pto", "leave"]
        },
        "MEALS": {
            "type": "Missed Meals",
            "description": "Missed Meal Claims",
            "guideline": "No outstanding claims",
            "keywords": ["meal", "missed meal", "food", "lunch", "dinner", "claim"]
        },
        "OVER": {
            "type": "Overtime",
            "description": "Overtime Requests outstanding",
            "guideline": "No outstanding requests",
            "keywords": ["overtime", "ot", "extra hours", "hours"]
        }
    }

    def __init__(self, model="openai/gpt-4o", site_url="", site_name=""):
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=API_KEY,
        )
        self.model = model
        self.site_url = site_url
        self.site_name = site_name

        # Session state
        self.active_session = False
        self.paramedic_name = None
        self.checklist_status = {}  # code -> {"status": "good/bad/unknown", "issues": 0, "notes": ""}
        self.conversation_history = []

    def is_checklist_request(self, user_message):
        """Detect if user wants to fill the daily checklist."""
        keywords = [
            "checklist", "daily check", "start my shift", "beginning of shift",
            "shift check", "pre-shift", "check list", "paramedic checklist",
            "fill checklist", "do my checklist", "complete checklist",
            "run through checklist", "go through checklist"
        ]
        message_lower = user_message.lower()
        return any(keyword in message_lower for keyword in keywords)

    def start_session(self, paramedic_name=None):
        """Start a new checklist session."""
        self.active_session = True
        self.paramedic_name = paramedic_name
        self.checklist_status = {
            code: {"status": "unknown", "issues": 0, "notes": ""}
            for code in self.CHECKLIST_ITEMS
        }
        self.conversation_history = []

    def detect_item_and_status(self, user_message):
        """
        Use AI to detect which checklist item the user is reporting on
        and what the status is (good/bad/issues count).
        """
        items_description = "\n".join([
            f"- {code}: {info['type']} - {info['description']}"
            for code, info in self.CHECKLIST_ITEMS.items()
        ])

        prompt = f"""
        A paramedic is reporting on their daily checklist. Determine which item(s) they're reporting on and the status.

        Available checklist items:
        {items_description}

        User message: "{user_message}"

        Return a JSON object with:
        - "items": array of objects, each with:
          - "code": the item code (e.g., "ACRc", "CERT-DL")
          - "status": "good" or "bad"
          - "issues": number of outstanding issues (0 if good, or a number if mentioned)
          - "notes": any additional notes mentioned

        If the user mentions multiple items, include all of them.
        If you can't determine which item, return empty items array.
        
        Return ONLY valid JSON.
        """

        completion = self.client.chat.completions.create(
            extra_headers={
                "HTTP-Referer": self.site_url,
                "X-OpenRouter-Title": self.site_name,
            },
            model=self.model,
            messages=[
                {"role": "system", "content": "Extract checklist item status. Output only valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
        )

        response = completion.choices[0].message.content.strip()
        if response.startswith("```"):
            response = response.split("\n", 1)[1] if "\n" in response else response[3:]
        if response.endswith("```"):
            response = response[:-3]

        try:
            result = json.loads(response.strip())
            return result.get("items", [])
        except json.JSONDecodeError:
            return []

    def update_status(self, items):
        """Update checklist status with detected items."""
        updated = []
        for item in items:
            code = item.get("code")
            if code in self.checklist_status:
                self.checklist_status[code] = {
                    "status": item.get("status", "unknown"),
                    "issues": item.get("issues", 0),
                    "notes": item.get("notes", "")
                }
                updated.append(code)
        return updated

    def get_remaining_items(self):
        """Get items not yet checked."""
        return [
            code for code, status in self.checklist_status.items()
            if status["status"] == "unknown"
        ]

    def get_completed_items(self):
        """Get items that have been checked."""
        return {
            code: status for code, status in self.checklist_status.items()
            if status["status"] != "unknown"
        }

    def get_items_with_issues(self):
        """Get items marked as bad or with issues > 0."""
        return {
            code: status for code, status in self.checklist_status.items()
            if status["status"] == "bad" or status["issues"] > 0
        }

    def is_complete(self):
        """Check if all items have been checked."""
        return all(s["status"] != "unknown" for s in self.checklist_status.values())

    def generate_next_prompt(self):
        """Generate a prompt asking about remaining items."""
        remaining = self.get_remaining_items()
        if not remaining:
            return None

        # Pick 2-3 items to ask about
        items_to_ask = remaining[:3]
        item_names = [self.CHECKLIST_ITEMS[code]["type"] for code in items_to_ask]

        if len(item_names) == 1:
            return f"How about your {item_names[0]}?"
        else:
            return f"What about your {', '.join(item_names[:-1])} or {item_names[-1]}?"

    def process_message(self, user_message):
        """
        Process user message for checklist updates.
        Returns dict with action, updated items, remaining, etc.
        """
        self.conversation_history.append({"role": "user", "content": user_message})

        # If no active session, check if starting one
        if not self.active_session:
            if self.is_checklist_request(user_message):
                self.start_session()
                return {
                    "action": "start_checklist",
                    "updated": [],
                    "completed": {},
                    "remaining": list(self.CHECKLIST_ITEMS.keys()),
                    "issues": {},
                    "is_complete": False,
                    "next_prompt": "Let's go through your checklist. Just tell me what's good or if you have any issues. What would you like to report first?"
                }
            return {
                "action": "no_checklist",
                "updated": [],
                "completed": {},
                "remaining": [],
                "issues": {},
                "is_complete": False,
                "next_prompt": None
            }

        # Active session - detect and update items
        detected_items = self.detect_item_and_status(user_message)
        updated_codes = self.update_status(detected_items)

        remaining = self.get_remaining_items()
        is_complete = self.is_complete()
        issues = self.get_items_with_issues()

        if is_complete:
            action = "complete_checklist"
            if issues:
                next_prompt = f"Checklist complete! You have {len(issues)} item(s) needing attention. Want me to summarize?"
            else:
                next_prompt = "All done! Everything looks good. Ready to start your shift!"
        elif updated_codes:
            action = "update_checklist"
            next_prompt = self.generate_next_prompt()
        else:
            action = "no_match"
            next_prompt = "I didn't catch which item that was. You can report on: " + ", ".join(
                [self.CHECKLIST_ITEMS[code]["type"] for code in remaining[:4]]
            )

        return {
            "action": action,
            "updated": updated_codes,
            "completed": self.get_completed_items(),
            "remaining": remaining,
            "issues": issues,
            "is_complete": is_complete,
            "next_prompt": next_prompt
        }

    def get_summary(self):
        """Generate a summary of the checklist status."""
        completed = self.get_completed_items()
        remaining = self.get_remaining_items()
        issues = self.get_items_with_issues()

        summary = "PARAMEDIC CHECKLIST\n"
        summary += "=" * 40 + "\n\n"

        if self.paramedic_name:
            summary += f"Paramedic: {self.paramedic_name}\n"
        summary += f"Date: {datetime.now().strftime('%m/%d/%Y')}\n\n"

        summary += "COMPLETED:\n"
        for code, status in completed.items():
            item = self.CHECKLIST_ITEMS[code]
            status_icon = "✓" if status["status"] == "good" else "✗"
            summary += f"  {status_icon} {item['type']}"
            if status["issues"] > 0:
                summary += f" ({status['issues']} issues)"
            if status["notes"]:
                summary += f" - {status['notes']}"
            summary += "\n"

        if remaining:
            summary += f"\nNOT YET CHECKED ({len(remaining)}):\n"
            for code in remaining:
                summary += f"  - {self.CHECKLIST_ITEMS[code]['type']}\n"

        if issues:
            summary += f"\nNEEDS ATTENTION ({len(issues)}):\n"
            for code, status in issues.items():
                item = self.CHECKLIST_ITEMS[code]
                summary += f"  ! {item['type']}: {status['issues']} outstanding\n"
                summary += f"    Guideline: {item['guideline']}\n"

        return summary

    def export_checklist(self, filepath=None):
        """Export checklist to JSON file."""
        if filepath is None:
            filepath = f"checklist_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        data = {
            "paramedic": self.paramedic_name,
            "date": datetime.now().isoformat(),
            "items": {
                code: {
                    "type": self.CHECKLIST_ITEMS[code]["type"],
                    "status": status["status"],
                    "issues": status["issues"],
                    "notes": status["notes"]
                }
                for code, status in self.checklist_status.items()
            },
            "is_complete": self.is_complete(),
            "has_issues": len(self.get_items_with_issues()) > 0
        }

        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)

        return filepath

    def end_session(self):
        """End the checklist session."""
        result = {
            "checklist_status": self.checklist_status.copy(),
            "is_complete": self.is_complete(),
            "issues": self.get_items_with_issues()
        }
        self.active_session = False
        self.checklist_status = {}
        self.conversation_history = []
        return result

    def cancel_session(self):
        """Cancel without completing."""
        self.active_session = False
        self.checklist_status = {}
        self.conversation_history = []
