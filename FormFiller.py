# form_filler.py
import json
import os
from openai import OpenAI
from dotenv import load_dotenv
from forms import FORMS

load_dotenv()
API_KEY = os.getenv("API_KEY")

class FormFiller:
    def __init__(self, model="openai/gpt-4o", site_url="", site_name=""):
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=API_KEY,
        )
        self.model = model
        self.site_url = site_url
        self.site_name = site_name
        self.forms = FORMS

    def select_form(self, transcription):
        """
        Use AI to choose the most appropriate form based on transcription.
        Returns the selected form template (dict).
        """
        form_names = [f["name"] for f in self.forms]
        prompt = f"""
        Based on the following paramedic's audio transcription, choose the most appropriate form from the list.
        Return ONLY the exact form name from the list, nothing else.

        Transcription:
        \"\"\"
        {transcription}
        \"\"\"

        Available forms: {', '.join(form_names)}
        """

        completion = self.client.chat.completions.create(
            extra_headers={
                "HTTP-Referer": self.site_url,
                "X-OpenRouter-Title": self.site_name,
            },
            model=self.model,
            messages=[
                {"role": "system", "content": "You output only the form name, nothing else."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
        )

        selected_name = completion.choices[0].message.content.strip()
        # Find matching form (case‑insensitive)
        for form in self.forms:
            if form["name"].lower() == selected_name.lower():
                return form
        # Fallback to first form if AI returns unexpected
        return self.forms[0]

    def fill_form(self, transcription, form_template):
        """
        Use AI to fill the fields of the given form template based on the transcription.
        Returns a dict with field names as keys and filled values.
        """
        fields_str = ", ".join(form_template["fields"])
        prompt = f"""
        You are in a office enviroment, no patients are present.
        You are the paperwork assistant filling out a one of the {form_template['name']} forms.
        Based on the audio transcription below, fill in the following fields as accurately as possible.
        If a field cannot be determined, set it to "unknown".
        Return ONLY a valid JSON object with the field names as keys.

        Transcription:
        \"\"\"
        {transcription}
        \"\"\"

        Fields: {fields_str}
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

        response = completion.choices[0].message.content
        # Clean possible markdown fences
        if response.startswith("```json"):
            response = response[7:]
        if response.startswith("```"):
            response = response[3:]
        if response.endswith("```"):
            response = response[:-3]
        filled_data = json.loads(response.strip())
        return filled_data

    def process(self, transcription):
        """
        High‑level method: select form, fill it, return (form_name, filled_data).
        """
        form = self.select_form(transcription)
        filled = self.fill_form(transcription, form)
        return form["name"], filled