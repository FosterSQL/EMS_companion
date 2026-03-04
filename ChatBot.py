# chatbot.py
from openai import OpenAI
import os

from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("API_KEY")

class ChatBot:
    def __init__(self, model="openai/gpt-4o", system_prompt=None, site_url="", site_name=""):
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=API_KEY,
        )
        self.model = model
        self.site_url = site_url
        self.site_name = site_name
        self.messages = []
        if system_prompt:
            self.messages.append({"role": "system", "content": system_prompt})

    def send_message(self, user_input, stream=True):
        """Send a message and return the full response (or a generator if stream=True)."""
        self.messages.append({"role": "user", "content": user_input})

        completion = self.client.chat.completions.create(
            extra_headers={
                "HTTP-Referer": self.site_url,
                "X-OpenRouter-Title": self.site_name,
            },
            model=self.model,
            messages=self.messages,
            stream=stream,
        )

        if stream:
            def generate():
                full = ""
                for chunk in completion:
                    if chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        full += content
                        yield content
                self.messages.append({"role": "assistant", "content": full})
            return generate()
        else:
            full = completion.choices[0].message.content
            self.messages.append({"role": "assistant", "content": full})
            return full