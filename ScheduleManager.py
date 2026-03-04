# ScheduleManager.py
import os
import re
import requests
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("API_KEY")


class ScheduleManager:
    """
    Manages paramedic schedule queries by fetching real-time calendar data
    from the EAI Ambulance Service website.
    """

    CALENDAR_URLS = {
        "march-2026": "https://effectiveai.net/calendars/march-2026.html",
        "april-2026": "https://effectiveai.net/calendars/april-2026.html",
    }

    def __init__(self, model="openai/gpt-4o", site_url="", site_name=""):
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=API_KEY,
        )
        self.model = model
        self.site_url = site_url
        self.site_name = site_name
        self.cached_schedules = {}

    def fetch_calendar(self, month_year):
        """
        Fetch calendar HTML from the website.
        month_year: e.g., "march-2026" or "april-2026"
        """
        url = self.CALENDAR_URLS.get(month_year.lower())
        if not url:
            return None

        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            print(f"Error fetching calendar: {e}")
            return None

    def parse_schedule_text(self, html_content):
        """
        Extract readable schedule text from HTML content.
        """
        # Remove HTML tags but preserve structure
        text = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>', '', html_content, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        return text

    def get_relevant_calendars(self, query):
        """
        Determine which calendar months are relevant to the query.
        Returns list of month-year keys.
        """
        query_lower = query.lower()
        relevant = []

        # Check for specific month mentions
        if "march" in query_lower or "mar" in query_lower:
            relevant.append("march-2026")
        if "april" in query_lower or "apr" in query_lower:
            relevant.append("april-2026")

        # If no specific month mentioned, get current month and next
        if not relevant:
            # Current date is March 4, 2026
            relevant = ["march-2026", "april-2026"]

        return relevant

    def fetch_schedule_data(self, months=None):
        """
        Fetch and cache schedule data for specified months.
        Returns combined schedule text.
        """
        if months is None:
            months = list(self.CALENDAR_URLS.keys())

        schedule_texts = []

        for month in months:
            # Check cache first
            if month not in self.cached_schedules:
                html = self.fetch_calendar(month)
                if html:
                    self.cached_schedules[month] = self.parse_schedule_text(html)

            if month in self.cached_schedules:
                schedule_texts.append(f"=== {month.upper()} SCHEDULE ===\n{self.cached_schedules[month]}")

        return "\n\n".join(schedule_texts)

    def is_schedule_query(self, user_message):
        """
        Detect if the user is asking about schedules/shifts.
        Returns True if schedule-related, False otherwise.
        """
        schedule_keywords = [
            "schedule", "shift", "working", "work", "calendar",
            "when am i", "when do i", "who is working", "who's working",
            "my shift", "next shift", "today", "tomorrow", "this week",
            "partner", "unit", "team", "assigned", "roster",
            "day off", "off day", "vacation", "coverage"
        ]

        query_lower = user_message.lower()
        return any(keyword in query_lower for keyword in schedule_keywords)

    def extract_query_details(self, user_message):
        """
        Extract specific details from the user's schedule query.
        Returns dict with: team, date, location, shift_type
        """
        prompt = f"""
        Extract schedule query details from this message. Return a JSON object with:
        - "team": team number if mentioned (e.g., "Team01", "Team25") or null
        - "date": specific date if mentioned (e.g., "March 4", "tomorrow", "today") or null
        - "location": location if mentioned (e.g., "Main St.", "Woodgrove", "Bedford", "Coral") or null
        - "unit": unit number if mentioned (e.g., "1122", "2233") or null
        - "shift_type": "day" or "night" if specified, or null
        - "query_type": one of "who_working", "my_schedule", "team_schedule", "general"
        
        Today is March 4, 2026.
        
        Message: "{user_message}"
        
        Return ONLY valid JSON, no markdown.
        """
        
        completion = self.client.chat.completions.create(
            extra_headers={
                "HTTP-Referer": self.site_url,
                "X-OpenRouter-Title": self.site_name,
            },
            model=self.model,
            messages=[
                {"role": "system", "content": "Extract query details. Output only valid JSON."},
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
            import json
            return json.loads(response.strip())
        except:
            return {"team": None, "date": None, "location": None, "unit": None, "shift_type": None, "query_type": "general"}

    def answer_schedule_query(self, user_message, user_team=None):
        """
        Answer a schedule-related query using real-time calendar data.
        Extracts specific details for more targeted, shorter responses.
        
        Args:
            user_message: The user's question about the schedule
            user_team: Optional team identifier (e.g., "Team01")
        
        Returns:
            Answer string
        """
        # Extract specific query details
        details = self.extract_query_details(user_message)
        
        # Determine which calendars to fetch
        relevant_months = self.get_relevant_calendars(user_message)

        # Fetch schedule data
        schedule_data = self.fetch_schedule_data(relevant_months)

        if not schedule_data:
            return "I couldn't retrieve the schedule information. Please try again later."

        # Build a focused prompt based on extracted details
        focus_parts = []
        if details.get("team"):
            focus_parts.append(f"Focus on {details['team']}")
        if details.get("date"):
            focus_parts.append(f"for {details['date']}")
        if details.get("location"):
            focus_parts.append(f"at {details['location']}")
        if details.get("unit"):
            focus_parts.append(f"Unit {details['unit']}")
        if details.get("shift_type"):
            focus_parts.append(f"{details['shift_type']} shift")
        
        focus_instruction = ". ".join(focus_parts) + "." if focus_parts else ""

        # Build prompt for AI to answer the question
        system_prompt = f"""You are a helpful paramedic scheduling assistant.
Answer questions about the EAI Ambulance Service schedule based on the calendar data provided.

IMPORTANT: Keep answers SHORT and DIRECT. 
- If asking about a specific team: just give their shifts, nothing else
- If asking who's working: only list relevant teams for that time/location
- Don't list the entire day's schedule unless specifically asked
- Use 1-2 sentences max when possible

Today's date is March 4, 2026.
{focus_instruction}"""

        user_prompt = f"""Schedule data:
{schedule_data}

Question: {user_message}

Give a SHORT, direct answer. Only include what was specifically asked."""

        if user_team:
            user_prompt += f"\n\nNote: The user is from {user_team}."

        completion = self.client.chat.completions.create(
            extra_headers={
                "HTTP-Referer": self.site_url,
                "X-OpenRouter-Title": self.site_name,
            },
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3,
        )

        raw_answer = completion.choices[0].message.content.strip()
        
        # Make the response more human and conversational
        return self._humanize_response(raw_answer)
    
    def _humanize_response(self, raw_response):
        """
        Make the schedule response more natural and conversational.
        """
        prompt = f"""Take this schedule information and make it sound natural, like a helpful coworker talking.

Rules:
- Keep it to 1-2 SHORT sentences max
- Be casual and friendly
- Don't say "based on the schedule" or similar
- Just tell them directly like you're chatting
- Use contractions (they're, you're, it's)

Original: "{raw_response}"

Rewrite it naturally:"""

        completion = self.client.chat.completions.create(
            extra_headers={
                "HTTP-Referer": self.site_url,
                "X-OpenRouter-Title": self.site_name,
            },
            model=self.model,
            messages=[
                {"role": "system", "content": "You're a friendly coworker. Keep responses super short and casual."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
        )

        return completion.choices[0].message.content.strip()

    def get_team_schedule(self, team_id, month=None):
        """
        Get the full schedule for a specific team.
        
        Args:
            team_id: Team identifier (e.g., "Team01" or "01")
            month: Optional month to filter (e.g., "march-2026")
        
        Returns:
            Schedule information for the team
        """
        # Normalize team ID
        if not team_id.lower().startswith("team"):
            team_id = f"Team{team_id.zfill(2)}"

        months = [month] if month else list(self.CALENDAR_URLS.keys())
        schedule_data = self.fetch_schedule_data(months)

        if not schedule_data:
            return f"Couldn't retrieve schedule for {team_id}."

        prompt = f"""From this schedule data, extract ALL shifts for {team_id}:

{schedule_data}

List each shift with:
- Date
- Location
- Unit
- Shift time
- Partner team

Format as a clear list."""

        completion = self.client.chat.completions.create(
            extra_headers={
                "HTTP-Referer": self.site_url,
                "X-OpenRouter-Title": self.site_name,
            },
            model=self.model,
            messages=[
                {"role": "system", "content": "Extract and list schedule information clearly."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
        )

        return completion.choices[0].message.content.strip()

    def get_todays_schedule(self):
        """Get the schedule for today (March 4, 2026)."""
        return self.answer_schedule_query("What is the full schedule for today, March 4, 2026?")

    def clear_cache(self):
        """Clear the cached schedule data to force fresh fetch."""
        self.cached_schedules = {}
