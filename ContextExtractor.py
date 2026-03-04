# context_extractor.py
import json
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("API_KEY")

class ContextExtractor:
    def __init__(self, model="openai/gpt-4o", site_url="", site_name=""):
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=API_KEY,
        )
        self.model = model
        self.site_url = site_url
        self.site_name = site_name

    def extract(self, text, output_path=None):
        """
        Extract structured fields from text.
        Returns a dict. If output_path is given, appends the dict to that JSON file.
        """
        prompt = f"""
        Analyze the following text and extract key information. Return ONLY a valid JSON object with these exact keys:
        - "where": location(s) mentioned (if any, otherwise null)
        - "what": main event or subject
        - "when": time or date mentioned (if any, otherwise null)
        - "why": reason or purpose (if any, otherwise null)
        - "who": people or entities involved
        - "how": method or manner (if any, otherwise null)
        - "brief_description": a concise summary of the text (max 2 sentences)

        Text:
        \"\"\"
        {text}
        \"\"\"
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
        data = json.loads(response.strip())

        if output_path:
            # Append to existing JSON list
            if os.path.exists(output_path):
                with open(output_path, "r", encoding="utf-8") as f:
                    existing = json.load(f)
                if isinstance(existing, list):
                    existing.append(data)
                else:
                    existing = [existing, data]
            else:
                existing = [data]
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(existing, f, indent=2, ensure_ascii=False)

        return data