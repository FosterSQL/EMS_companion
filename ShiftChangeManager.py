# ShiftChangeManager.py
import os
import json
import requests
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("API_KEY")


class ShiftChangeManager:
    """
    Manages shift change requests (SCR) - detects intent, collects info, submits form.
    """

    FORM_URL = "https://effectiveai.net/scr-form.html"
    
    REQUIRED_FIELDS = {
        "first_name": "First name",
        "last_name": "Last name",
        "medic_number": "Medic/badge number",
        "shift_day": "Date of the shift (mm/dd/yyyy)",
        "shift_start": "Shift start time",
        "shift_end": "Shift end time",
        "requested_action": "What you want to do (swap, drop, pick up, etc.)"
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
        self.collected_data = {}
        self.conversation_history = []
        self.last_asked_field = None

    def is_shift_change_request(self, user_message):
        """
        Detect if user is requesting a shift change.
        """
        import re
        message_lower = user_message.lower()
        
        # Exact phrase keywords
        keywords = [
            "shift change", "swap shift", "switch shift", "trade shift",
            "drop shift", "pick up shift", "cover shift", "shift swap",
            "request off", "time off", "scr", "shift request", 
            "can someone cover", "need coverage", "swap with", "trade with",
            "take my shift", "need to swap", "want to swap", "want to trade", 
            "want to switch", "modify shift", "modify my shift"
        ]
        
        if any(keyword in message_lower for keyword in keywords):
            return True
        
        # Pattern matching for "change/swap/switch/trade/drop/pick up ... shift"
        # This handles cases like "change my march 1st shift"
        shift_patterns = [
            r'\b(change|swap|switch|trade|drop|modify)\b.*\bshift\b',
            r'\bshift\b.*\b(change|swap|switch|trade|drop|modify)\b',
            r'\bpick\s*up\b.*\bshift\b',
            r'\bneed\s+(a\s+)?different\s+shift\b',
            r'\bcan.t\s+(work|make)\b.*\bshift\b',
            r'\b(move|reschedule)\b.*\bshift\b',
        ]
        
        for pattern in shift_patterns:
            if re.search(pattern, message_lower):
                return True
        
        return False

    def start_session(self):
        """Start a new shift change request session."""
        self.active_session = True
        self.collected_data = {field: None for field in self.REQUIRED_FIELDS}
        self.conversation_history = []
        self.last_asked_field = None

    def extract_field_values(self, user_message):
        """
        Extract field values from user message.
        """
        current_data = {k: v for k, v in self.collected_data.items() if v is not None}
        missing = self.get_missing_fields()
        
        # If we just asked for a specific field, the answer is likely for that field
        context_hint = ""
        if self.last_asked_field:
            context_hint = f"\nIMPORTANT: I just asked for '{self.last_asked_field.replace('_', ' ')}', so if the message is a direct answer, assign it to '{self.last_asked_field}'."
        
        prompt = f"""
        Extract shift change request details from this message.
        
        Current data collected:
        {json.dumps(current_data, indent=2) if current_data else "None yet"}
        
        Still missing: {', '.join(missing)}
        {context_hint}
        
        User message: "{user_message}"
        
        Extract any of these fields if mentioned:
        - first_name: person's first name
        - last_name: person's last name
        - medic_number: badge/medic number (digits)
        - shift_day: date in mm/dd/yyyy format (convert if needed, today is {datetime.now().strftime('%m/%d/%Y')})
        - shift_start: start time (e.g., "7:00 AM" or "07:00")
        - shift_end: end time (e.g., "7:00 PM" or "19:00")
        - requested_action: what they want (swap, drop, pick up, trade, etc.)
        
        Return ONLY a JSON object with fields that have values from this message.
        If the user gives a short answer like a name or number, match it to the appropriate field.
        """
        
        completion = self.client.chat.completions.create(
            extra_headers={
                "HTTP-Referer": self.site_url,
                "X-OpenRouter-Title": self.site_name,
            },
            model=self.model,
            messages=[
                {"role": "system", "content": "Extract form data. Output only valid JSON. If given a short answer, match it to the likely field based on context."},
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
            new_values = json.loads(response.strip())
            # Update collected data
            for field, value in new_values.items():
                if field in self.collected_data and value:
                    self.collected_data[field] = value
            return new_values
        except json.JSONDecodeError:
            return {}

    def get_missing_fields(self):
        """Return list of fields still needed."""
        return [f for f, v in self.collected_data.items() if v is None]

    def get_collected_fields(self):
        """Return dict of fields with values."""
        return {f: v for f, v in self.collected_data.items() if v is not None}

    def is_complete(self):
        """Check if all required fields are collected."""
        return all(v is not None for v in self.collected_data.values())

    def generate_question_for_missing(self):
        """Generate a natural question for missing fields."""
        missing = self.get_missing_fields()
        if not missing:
            self.last_asked_field = None
            return None
        
        collected = self.get_collected_fields()
        
        # Prioritize fields in logical order
        priority_order = ["first_name", "last_name", "medic_number", "shift_day", "shift_start", "shift_end", "requested_action"]
        next_field = None
        for field in priority_order:
            if field in missing:
                next_field = field
                break
        
        if not next_field:
            next_field = missing[0]
        
        # Track what we just asked for context
        self.last_asked_field = next_field
        
        # Direct questions for each field
        direct_questions = {
            "first_name": "What's your first name?",
            "last_name": "And your last name?",
            "medic_number": "What's your medic or badge number?",
            "shift_day": "What date is the shift you want to change?",
            "shift_start": "What time does that shift start?",
            "shift_end": "And what time does it end?",
            "requested_action": "What do you want to do - swap it, drop it, or pick up a different one?"
        }
        
        return direct_questions.get(next_field, f"What's the {next_field.replace('_', ' ')}?")

    def process_message(self, user_message):
        """
        Process a user message for shift change request.
        Returns dict with action, extracted data, missing fields, etc.
        """
        self.conversation_history.append({"role": "user", "content": user_message})
        
        # If no active session, check if this starts one
        if not self.active_session:
            if self.is_shift_change_request(user_message):
                self.start_session()
                extracted = self.extract_field_values(user_message)
                missing = self.get_missing_fields()
                
                return {
                    "action": "start_scr",
                    "extracted": extracted,
                    "collected": self.get_collected_fields(),
                    "missing": missing,
                    "is_complete": self.is_complete(),
                    "next_question": self.generate_question_for_missing() if missing else None
                }
            else:
                return {
                    "action": "no_scr",
                    "extracted": {},
                    "collected": {},
                    "missing": [],
                    "is_complete": False,
                    "next_question": None
                }
        
        # Active session - extract new values
        extracted = self.extract_field_values(user_message)
        missing = self.get_missing_fields()
        is_complete = self.is_complete()
        
        if is_complete:
            return {
                "action": "complete_scr",
                "extracted": extracted,
                "collected": self.get_collected_fields(),
                "missing": [],
                "is_complete": True,
                "next_question": None
            }
        else:
            return {
                "action": "update_scr",
                "extracted": extracted,
                "collected": self.get_collected_fields(),
                "missing": missing,
                "is_complete": False,
                "next_question": self.generate_question_for_missing()
            }

    def submit_form(self):
        """
        Submit the shift change request form.
        Returns (success: bool, message: str)
        """
        if not self.is_complete():
            return False, "Cannot submit - missing required fields."
        
        # Prepare form data
        form_data = {
            "firstName": self.collected_data["first_name"],
            "lastName": self.collected_data["last_name"],
            "medicNumber": self.collected_data["medic_number"],
            "shiftDay": self.collected_data["shift_day"],
            "shiftStart": self.collected_data["shift_start"],
            "shiftEnd": self.collected_data["shift_end"],
            "requestedAction": self.collected_data["requested_action"]
        }
        
        try:
            # Try to submit the form
            # Note: The actual form submission endpoint may vary
            # This attempts common patterns
            
            # Try posting to the same URL or a submit endpoint
            submit_urls = [
                "https://effectiveai.net/scr-form.html",
                "https://effectiveai.net/api/scr",
                "https://effectiveai.net/submit-scr"
            ]
            
            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "ParamedicVoiceAssistant/1.0"
            }
            
            for url in submit_urls:
                try:
                    response = requests.post(url, data=form_data, headers=headers, timeout=10)
                    if response.status_code in [200, 201, 302]:
                        self.end_session()
                        return True, f"Shift change request submitted successfully for {self.collected_data['first_name']} {self.collected_data['last_name']}!"
                except:
                    continue
            
            # If direct submission fails, save locally and notify
            filename = f"SCR_{self.collected_data['last_name']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(filename, 'w') as f:
                json.dump({
                    "form_url": self.FORM_URL,
                    "submitted_at": datetime.now().isoformat(),
                    "data": form_data
                }, f, indent=2)
            
            self.end_session()
            return True, f"Request saved to {filename}. Please submit manually at {self.FORM_URL}"
            
        except Exception as e:
            return False, f"Submission error: {str(e)}"

    def end_session(self):
        """End the current session."""
        result = {
            "collected_data": self.collected_data.copy(),
            "is_complete": self.is_complete()
        }
        self.active_session = False
        self.collected_data = {}
        self.conversation_history = []
        return result

    def get_summary(self):
        """Get a summary of the current request."""
        if not self.active_session:
            return "No active shift change request."
        
        collected = self.get_collected_fields()
        missing = self.get_missing_fields()
        
        summary = "SHIFT CHANGE REQUEST\n"
        summary += "-" * 30 + "\n"
        
        for field, label in self.REQUIRED_FIELDS.items():
            value = collected.get(field, "[ needed ]")
            summary += f"{label}: {value}\n"
        
        if missing:
            summary += f"\nStill need: {', '.join([self.REQUIRED_FIELDS[f] for f in missing])}"
        else:
            summary += "\n✓ Ready to submit!"
        
        return summary

    def cancel_session(self):
        """Cancel without submitting."""
        self.active_session = False
        self.collected_data = {}
        self.conversation_history = []
