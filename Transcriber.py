# transcriber.py
import base64
import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("API_KEY")

class Transcriber:
    def __init__(self,  model="openai/gpt-4o-audio-preview", site_url="", site_name=""):
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=API_KEY,
        )
        self.model = model
        self.site_url = site_url
        self.site_name = site_name

    def is_paramedic_related(self, text):
        """
        Determine if the transcribed text is paramedic/medical/EMS related.
        Returns True if paramedic-related, False otherwise.
        """
        prompt = f"""
        Determine if this text is related to paramedic paper work 
        
        Return ONLY "yes" or "no", nothing else.
        
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
            model="openai/gpt-4o",  # Use text model, not audio model
            messages=[
                {"role": "system", "content": "You output only 'yes' or 'no'."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
        )
        
        response = completion.choices[0].message.content.strip().lower()
        return response == "yes"

    def transcribe(self, audio_path, past_context=None, output_path=None):
        """Transcribe audio file and return text. Optionally save to output_path."""
        with open(audio_path, "rb") as f:
            base64_audio = base64.b64encode(f.read()).decode('utf-8')

        # First, do a quick transcription without context to check relevance
        messages = []
        system_content = (
            "You are a transcription assistant. "
            "Transcribe the audio EXACTLY as spoken — word for word. "
            "Do NOT summarize, interpret, or add commentary. "
            "Output ONLY the verbatim transcription."
        )
        messages.append({
            "role": "system",
            "content": system_content
        })

        messages.append({
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "Transcribe this audio recording exactly as spoken. Output only the verbatim transcription, nothing else."
                },
                {
                    "type": "input_audio",
                    "input_audio": {
                        "data": base64_audio,
                        "format": "wav"
                    }
                }
            ]
        })

        completion = self.client.chat.completions.create(
            extra_headers={
                "HTTP-Referer": self.site_url,
                "X-OpenRouter-Title": self.site_name,
            },
            model=self.model,
            messages=messages,
        )

        text = completion.choices[0].message.content
        
        # Check if content is paramedic-related
        # Only use context if it's paramedic-related AND context was provided
        if past_context and self.is_paramedic_related(text):
            # Re-transcribe with context for better medical terminology
            messages_with_context = []
            system_content_with_context = (
                "You are a transcription assistant for paramedic audio recordings. "
                "A paramedic is speaking directly to you (the AI assistant). "
                "Your job is to transcribe the audio EXACTLY as spoken — word for word. "
                "Do NOT summarize, interpret, or add commentary. "
                "Do NOT infer or fabricate any details not explicitly spoken. "
                "Output ONLY the verbatim transcription of what the paramedic says. "
                "Remember: this is direct communication from the paramedic to you."
            )
            system_content_with_context += (
                f"\n\nFor reference, here is recent context from previous interactions "
                f"that may help with names, locations, or medical terminology:\n{past_context}\n"
                f"Use this ONLY to help with spelling/terminology — do NOT let it influence "
                f"what words you transcribe from this audio."
            )
            messages_with_context.append({
                "role": "system",
                "content": system_content_with_context
            })

            messages_with_context.append({
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Transcribe this audio recording exactly as spoken. Output only the verbatim transcription, nothing else."
                    },
                    {
                        "type": "input_audio",
                        "input_audio": {
                            "data": base64_audio,
                            "format": "wav"
                        }
                    }
                ]
            })

            completion = self.client.chat.completions.create(
                extra_headers={
                    "HTTP-Referer": self.site_url,
                    "X-OpenRouter-Title": self.site_name,
                },
                model=self.model,
                messages=messages_with_context,
            )

            text = completion.choices[0].message.content
        
        if output_path:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(text)
                f.write(f"\n\n--- TOKEN USAGE ---\n")
                f.write(f"Prompt tokens: {completion.usage.prompt_tokens}\n")
                f.write(f"Completion tokens: {completion.usage.completion_tokens}\n")
                f.write(f"Total tokens: {completion.usage.total_tokens}\n")
        return text