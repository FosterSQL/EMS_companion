# conversation_manager.py
import json
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("API_KEY")

class ConversationManager:
    def __init__(self, model="openai/gpt-4o", site_url="", site_name=""):
        """
        Manages conversations with intelligent intent detection and detail extraction.
        Stores key information from user messages for retrieval and context.
        """
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=API_KEY,
        )
        self.model = model
        self.site_url = site_url
        self.site_name = site_name
        
        # Store conversation data
        self.conversation_history = []  # Full message history
        self.extracted_details = {}     # Key details extracted from conversation
        self.conversation_summary = ""  # Overall summary

    def analyze_intent(self, user_message):
        """
        Analyze user message to determine primary intent.
        Returns one of: 'information_request', 'status_update', 'incident_report', 'question', 'other'
        """
        intent_types = [
            'information_request',  # User asking for information
            'status_update',        # User providing status/update
            'incident_report',      # User reporting an incident
            'question',             # General question
            'other'
        ]
        
        prompt = f"""
        Analyze the paramedic's message and determine their primary intent.
        Return ONLY the exact intent type from the list below, nothing else.
        
        Intent types: {', '.join(intent_types)}
        
        Message:
        \"\"\"
        {user_message}
        \"\"\"
        """
        
        completion = self.client.chat.completions.create(
            extra_headers={
                "HTTP-Referer": self.site_url,
                "X-OpenRouter-Title": self.site_name,
            },
            model=self.model,
            messages=[
                {"role": "system", "content": "You output only the intent type, nothing else."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
        )
        
        intent = completion.choices[0].message.content.strip().lower()
        return intent if intent in intent_types else 'other'

    def extract_details(self, user_message):
        """
        Extract key details from user message.
        Returns a dict with structured information.
        """
        prompt = f"""
        Extract key details from this paramedic's message. Return ONLY a valid JSON object.
        Include any of these categories that are mentioned:
        - patient_info: age, gender, condition, symptoms
        - location: where the incident occurred
        - time: when it happened
        - actions_taken: what has been done
        - resources_needed: equipment or assistance requested
        - observations: relevant observations
        
        If a category is not mentioned, set it to null.
        
        Message:
        \"\"\"
        {user_message}
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
        # Clean markdown fences
        if response.startswith("```json"):
            response = response[7:]
        if response.startswith("```"):
            response = response[3:]
        if response.endswith("```"):
            response = response[:-3]
        
        try:
            details = json.loads(response.strip())
        except json.JSONDecodeError:
            details = {}
        
        return details

    def add_message(self, user_message, assistant_response=None):
        """
        Add a message to conversation history and extract/store details.
        
        Args:
            user_message: The user's input
            assistant_response: Optional assistant response to store
        """
        # Analyze intent
        intent = self.analyze_intent(user_message)
        
        # Extract details
        details = self.extract_details(user_message)
        
        # Store in conversation history
        message_entry = {
            "role": "user",
            "content": user_message,
            "intent": intent,
            "extracted_details": details,
            "timestamp": None  # Can be added later if needed
        }
        self.conversation_history.append(message_entry)
        
        # Merge extracted details into overall storage
        self._merge_details(details)
        
        # Store assistant response if provided
        if assistant_response:
            self.conversation_history.append({
                "role": "assistant",
                "content": assistant_response
            })
        
        return {
            "intent": intent,
            "details": details
        }

    def _merge_details(self, new_details):
        """Merge newly extracted details with existing stored details."""
        for category, value in new_details.items():
            if value and value is not None:
                if category not in self.extracted_details:
                    self.extracted_details[category] = value
                else:
                    # Update existing details (can implement merge logic here)
                    if isinstance(value, dict):
                        self.extracted_details[category].update(value)
                    else:
                        self.extracted_details[category] = value

    def get_conversation_summary(self):
        """
        Generate a summary of the entire conversation.
        Returns a brief summary of all key points discussed.
        """
        if not self.conversation_history:
            return "No conversation yet."
        
        # Get all user messages
        user_messages = [msg["content"] for msg in self.conversation_history if msg["role"] == "user"]
        messages_text = "\n".join([f"- {msg}" for msg in user_messages])
        
        prompt = f"""
        Summarize this paramedic conversation in 2-3 sentences, focusing on key incidents, 
        actions taken, and current status.
        
        Messages:
        {messages_text}
        """
        
        completion = self.client.chat.completions.create(
            extra_headers={
                "HTTP-Referer": self.site_url,
                "X-OpenRouter-Title": self.site_name,
            },
            model=self.model,
            messages=[
                {"role": "system", "content": "You provide concise summaries."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
        )
        
        summary = completion.choices[0].message.content
        self.conversation_summary = summary
        return summary

    def get_extracted_details(self):
        """Return all extracted details stored from the conversation."""
        return self.extracted_details

    def get_detail_by_category(self, category):
        """Retrieve details for a specific category."""
        return self.extracted_details.get(category, None)

    def get_conversation_history(self):
        """Return the full conversation history."""
        return self.conversation_history

    def export_as_json(self, filepath=None):
        """
        Export conversation data as JSON.
        
        Args:
            filepath: Optional file path to save to
            
        Returns:
            JSON string of conversation data
        """
        data = {
            "conversation_history": self.conversation_history,
            "extracted_details": self.extracted_details,
            "summary": self.conversation_summary,
            "total_messages": len(self.conversation_history)
        }
        
        json_str = json.dumps(data, indent=2)
        
        if filepath:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(json_str)
            print(f"Conversation exported to {filepath}")
        
        return json_str

    def reset(self):
        """Clear all conversation data."""
        self.conversation_history = []
        self.extracted_details = {}
        self.conversation_summary = ""
