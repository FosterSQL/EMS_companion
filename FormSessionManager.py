# FormSessionManager.py
import json
import os
from openai import OpenAI
from dotenv import load_dotenv
from forms import FORMS

load_dotenv()
API_KEY = os.getenv("API_KEY")


class FormSessionManager:
    """
    Manages interactive form-filling sessions with the user.
    Detects form intent, tracks collected fields, and prompts for missing info.
    """

    def __init__(self, model="openai/gpt-4o", site_url="", site_name=""):
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=API_KEY,
        )
        self.model = model
        self.site_url = site_url
        self.site_name = site_name
        self.forms = FORMS

        # Session state
        self.active_session = False
        self.current_form = None
        self.collected_fields = {}
        self.conversation_history = []

    def detect_form_intent(self, user_message):
        """
        Detect if user wants to fill a form and which one.
        Returns: (wants_form: bool, form_name: str or None, confidence: str)
        """
        form_names = [f["name"] for f in self.forms]
        form_descriptions = {
            "Occurrence Report": "incident reports, accidents, unusual events, safety concerns",
            "Teddy Bear Tracking": "giving teddy bears to patients, children, families",
            "Shift Log": "shift start/end times, partner info, shift notes",
            "Equipment Request": "requesting supplies, equipment, inventory needs"
        }

        prompt = f"""
        Analyze this message from a paramedic and determine:
        1. Is the user trying to fill out or report information for a form?
        2. If yes, which form type matches best?

        Available forms:
        {json.dumps(form_descriptions, indent=2)}

        User message:
        \"\"\"{user_message}\"\"\"

        Return a JSON object with:
        - "wants_form": true/false
        - "form_name": exact form name from list or null
        - "confidence": "high", "medium", or "low"
        - "reasoning": brief explanation

        Return ONLY valid JSON, no markdown.
        """

        completion = self.client.chat.completions.create(
            extra_headers={
                "HTTP-Referer": self.site_url,
                "X-OpenRouter-Title": self.site_name,
            },
            model=self.model,
            messages=[
                {"role": "system", "content": "You output only valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
        )

        response = completion.choices[0].message.content.strip()
        # Clean markdown fences
        if response.startswith("```"):
            response = response.split("\n", 1)[1] if "\n" in response else response[3:]
        if response.endswith("```"):
            response = response[:-3]

        try:
            result = json.loads(response.strip())
            return (
                result.get("wants_form", False),
                result.get("form_name"),
                result.get("confidence", "low"),
                result.get("reasoning", "")
            )
        except json.JSONDecodeError:
            return False, None, "low", "Failed to parse response"

    def start_form_session(self, form_name):
        """
        Start a new form-filling session for the specified form.
        Returns the form fields that need to be collected.
        """
        # Find the form template
        form_template = None
        for form in self.forms:
            if form["name"].lower() == form_name.lower():
                form_template = form
                break

        if not form_template:
            return None

        self.active_session = True
        self.current_form = form_template
        self.collected_fields = {field: None for field in form_template["fields"]}
        self.conversation_history = []

        return form_template

    def extract_field_values(self, user_message):
        """
        Extract field values from user message for the current form.
        Updates collected_fields and returns newly extracted values.
        """
        if not self.active_session or not self.current_form:
            return {}

        fields_str = ", ".join(self.current_form["fields"])
        current_data = {k: v for k, v in self.collected_fields.items() if v is not None}

        # Field descriptions to help LLM understand what each field means
        field_hints = {
            "paramedic_id": "paramedic ID, badge number, medic number, employee ID, or any numeric ID",
            "paramedic_name": "paramedic's name, medic name, your name",
            "reported_by_id": "reporter's ID, badge number, employee ID",
            "reported_by_name": "reporter's name, your name",
            "recipient_type": "who received the teddy bear: Patient, Family, Bystander, or Other",
            "gender": "Male, Female, Other, or Prefer not to say",
            "date": "the date this happened",
            "incident_date": "the date of the incident",
            "incident_time": "the time of the incident",
            "shift_date": "the date of the shift",
            "start_time": "shift start time",
            "end_time": "shift end time",
            "location": "where this took place",
            "partner_name": "partner's name, crew partner",
        }

        # Build field descriptions for the current form
        field_descriptions = []
        for field in self.current_form["fields"]:
            hint = field_hints.get(field, field.replace("_", " "))
            field_descriptions.append(f"- {field}: {hint}")
        
        prompt = f"""
        You are helping fill a "{self.current_form['name']}" form.
        
        Current collected data:
        {json.dumps(current_data, indent=2) if current_data else "None yet"}

        The user just said:
        \"\"\"{user_message}\"\"\"

        Extract any field values for these fields:
        {chr(10).join(field_descriptions)}

        IMPORTANT: 
        - If the user mentions an ID number, badge number, or medic number, map it to "paramedic_id" or "reported_by_id" as appropriate.
        - Return the exact field names as shown above (with underscores).
        - Return a JSON object with ONLY the fields that have NEW values from this message.
        - If a field wasn't mentioned, don't include it.

        Return ONLY valid JSON, no markdown.
        """

        completion = self.client.chat.completions.create(
            extra_headers={
                "HTTP-Referer": self.site_url,
                "X-OpenRouter-Title": self.site_name,
            },
            model=self.model,
            messages=[
                {"role": "system", "content": "You output only valid JSON with field values. Use exact field names with underscores."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
        )

        response = completion.choices[0].message.content.strip()
        # Clean markdown fences
        if response.startswith("```"):
            response = response.split("\n", 1)[1] if "\n" in response else response[3:]
        if response.endswith("```"):
            response = response[:-3]

        try:
            new_values = json.loads(response.strip())
            # Update collected fields
            for field, value in new_values.items():
                if field in self.collected_fields and value:
                    self.collected_fields[field] = value
            return new_values
        except json.JSONDecodeError:
            return {}

    def get_missing_fields(self):
        """Return list of fields that still need values."""
        if not self.active_session:
            return []
        return [f for f, v in self.collected_fields.items() if v is None]

    def get_collected_fields(self):
        """Return dict of fields that have values."""
        if not self.active_session:
            return {}
        return {f: v for f, v in self.collected_fields.items() if v is not None}

    def is_form_complete(self):
        """Check if all required fields have been collected."""
        if not self.active_session:
            return False
        return all(v is not None for v in self.collected_fields.values())

    def generate_prompt_for_missing(self):
        """
        Generate a natural question asking for missing fields.
        Returns a conversational prompt for the assistant to speak.
        """
        missing = self.get_missing_fields()
        if not missing:
            return None

        # Group fields into natural questions
        if len(missing) == 1:
            field = missing[0].replace("_", " ")
            prompt = f"What's the {field}?"
        elif len(missing) <= 3:
            fields = [f.replace("_", " ") for f in missing]
            prompt = f"I still need: {', '.join(fields)}. Can you provide those?"
        else:
            # Prioritize most common/important fields first
            priority_fields = missing[:3]
            fields = [f.replace("_", " ") for f in priority_fields]
            prompt = f"Let's start with: {', '.join(fields)}?"

        return prompt

    def generate_smart_question(self):
        """
        Use AI to generate a natural, conversational question for missing fields.
        """
        missing = self.get_missing_fields()
        if not missing:
            return None

        collected = self.get_collected_fields()

        prompt = f"""
        You're a paramedic assistant helping fill a "{self.current_form['name']}" form.
        
        Already collected:
        {json.dumps(collected, indent=2) if collected else "Nothing yet"}
        
        Still need:
        {', '.join(missing)}
        
        Generate a SHORT, natural question (1 sentence) to ask for the next missing info.
        Focus on the most important missing field.
        Be conversational, like talking to a colleague.
        """

        completion = self.client.chat.completions.create(
            extra_headers={
                "HTTP-Referer": self.site_url,
                "X-OpenRouter-Title": self.site_name,
            },
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant. Output only the question, nothing else."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
        )

        return completion.choices[0].message.content.strip()

    def process_message(self, user_message):
        """
        Main entry point for processing user messages during form filling.
        Returns a dict with:
        - action: "start_form", "update_form", "complete_form", "no_form", "continue_conversation"
        - form_name: if applicable
        - extracted: newly extracted field values
        - missing: list of still-missing fields
        - collected: all collected field values
        - next_question: what to ask the user next
        - is_complete: whether form is now complete
        """
        # Add to conversation history
        self.conversation_history.append({
            "role": "user",
            "content": user_message
        })

        # If no active session, check if user wants to start one
        if not self.active_session:
            wants_form, form_name, confidence, reasoning = self.detect_form_intent(user_message)

            if wants_form and form_name and confidence in ["high", "medium"]:
                # Start new session
                form = self.start_form_session(form_name)
                if form:
                    # Extract any values from initial message
                    extracted = self.extract_field_values(user_message)
                    missing = self.get_missing_fields()
                    next_question = self.generate_smart_question() if missing else None

                    return {
                        "action": "start_form",
                        "form_name": form_name,
                        "extracted": extracted,
                        "missing": missing,
                        "collected": self.get_collected_fields(),
                        "next_question": next_question,
                        "is_complete": self.is_form_complete()
                    }

            # No form intent detected
            return {
                "action": "no_form",
                "form_name": None,
                "extracted": {},
                "missing": [],
                "collected": {},
                "next_question": None,
                "is_complete": False
            }

        # Active session - extract new values
        extracted = self.extract_field_values(user_message)
        missing = self.get_missing_fields()
        is_complete = self.is_form_complete()

        if is_complete:
            action = "complete_form"
            next_question = None
        else:
            action = "update_form"
            next_question = self.generate_smart_question()

        return {
            "action": action,
            "form_name": self.current_form["name"],
            "extracted": extracted,
            "missing": missing,
            "collected": self.get_collected_fields(),
            "next_question": next_question,
            "is_complete": is_complete
        }

    def end_session(self):
        """End the current form session and return final data."""
        if not self.active_session:
            return None

        result = {
            "form_name": self.current_form["name"],
            "fields": self.collected_fields.copy(),
            "is_complete": self.is_form_complete(),
            "conversation_history": self.conversation_history.copy()
        }

        # Reset state
        self.active_session = False
        self.current_form = None
        self.collected_fields = {}
        self.conversation_history = []

        return result

    def get_form_summary(self):
        """Generate a summary of the current form status."""
        if not self.active_session:
            return "No active form session."

        collected = self.get_collected_fields()
        missing = self.get_missing_fields()

        summary = f"Form: {self.current_form['name']}\n"
        summary += f"Collected ({len(collected)}/{len(self.collected_fields)}):\n"
        for field, value in collected.items():
            summary += f"  - {field.replace('_', ' ').title()}: {value}\n"

        if missing:
            summary += f"\nStill needed:\n"
            for field in missing:
                summary += f"  - {field.replace('_', ' ').title()}\n"
        else:
            summary += "\n✅ Form is complete!"

        return summary

    def cancel_session(self):
        """Cancel the current session without saving."""
        self.active_session = False
        self.current_form = None
        self.collected_fields = {}
        self.conversation_history = []
