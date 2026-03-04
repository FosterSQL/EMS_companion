# answer_builder.py
import os
import json
import subprocess
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("API_KEY")

class AnswerBuilder:
    def __init__(self, model="openai/gpt-4o", site_url="", site_name="", tts_engine="azure"):
        """
        Initialize AnswerBuilder for generating and voicing responses.
        
        Args:
            model: LLM model to use for generating answers (default: openai/gpt-4o)
            site_url: OpenRouter site URL for headers
            site_name: OpenRouter site name for headers
            tts_engine: TTS engine to use ("azure", "google", "elevenlabs", or "edge")
        """
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=API_KEY,
        )
        self.model = model
        self.site_url = site_url
        self.site_name = site_name
        self.tts_engine = tts_engine

    def generate_answer(self, query, context=None, system_prompt=None, stream=False):
        """
        Generate an AI response to a query.
        
        Args:
            query: The question/prompt to answer
            context: Optional context to include in the prompt
            system_prompt: Optional custom system prompt
            stream: Whether to stream the response
            
        Returns:
            Full response text (or generator if stream=True)
        """
        if system_prompt is None:
            system_prompt = (
                "You are a friendly paramedic assistant chatting with a colleague during their shift. "
                "You're warm, supportive, and genuinely care about their wellbeing. "
                "Keep responses SHORT (1-2 sentences max) but natural and caring. "
                "Use casual language like 'Hey', 'Sure thing', 'No worries', 'Got it'. "
                "Ask follow-up questions to keep the conversation flowing naturally."
            )
        
        messages = [{"role": "system", "content": system_prompt}]
        
        if context:
            messages.append({"role": "system", "content": f"Context: {context}"})
        
        messages.append({"role": "user", "content": query})
        
        completion = self.client.chat.completions.create(
            extra_headers={
                "HTTP-Referer": self.site_url,
                "X-OpenRouter-Title": self.site_name,
            },
            model=self.model,
            messages=messages,
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
                return full
            return generate()
        else:
            return completion.choices[0].message.content

    def text_to_speech(self, text, output_file="response_audio.mp3"):
        """
        Convert text to speech using the configured TTS engine.
        
        Args:
            text: Text to convert to speech
            output_file: Output audio file path
            
        Returns:
            Path to generated audio file
        """
        if self.tts_engine == "edge":
            return self._tts_edge(text, output_file)
        elif self.tts_engine == "google":
            return self._tts_google(text, output_file)
        elif self.tts_engine == "elevenlabs":
            return self._tts_elevenlabs(text, output_file)
        elif self.tts_engine == "azure":
            return self._tts_azure(text, output_file)
        else:
            raise ValueError(f"Unknown TTS engine: {self.tts_engine}")

    def _tts_edge(self, text, output_file):
        """Use Microsoft Edge TTS (free, no API key needed)."""
        try:
            import edge_tts
            import asyncio
            
            async def generate():
                communicate = edge_tts.Communicate(text=text, voice="en-US-AriaNeural")
                await communicate.save(output_file)
            
            asyncio.run(generate())
            print(f"Audio saved to {output_file}")
            return output_file
        except ImportError:
            raise ImportError("edge-tts not installed. Run: pip install edge-tts")

    def _tts_google(self, text, output_file):
        """Use Google Text-to-Speech API."""
        try:
            from google.cloud import texttospeech
            
            client = texttospeech.TextToSpeechClient()
            input_text = texttospeech.SynthesisInput(text=text)
            voice = texttospeech.VoiceSelectionParams(
                language_code="en-US",
                name="en-US-Neural2-A"
            )
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.MP3
            )
            
            response = client.synthesize_speech(
                input=input_text,
                voice=voice,
                audio_config=audio_config
            )
            
            with open(output_file, "wb") as out:
                out.write(response.audio_content)
            print(f"Audio saved to {output_file}")
            return output_file
        except ImportError:
            raise ImportError("google-cloud-texttospeech not installed. Run: pip install google-cloud-texttospeech")

    def _tts_elevenlabs(self, text, output_file):
        """Use ElevenLabs TTS API with multilingual v2 model and high-quality voice."""
        try:
            from elevenlabs.client import ElevenLabs
            
            api_key = os.getenv("ELEVENLABS_API_KEY")
            if not api_key:
                raise ValueError("ELEVENLABS_API_KEY not found in .env file")
            
            client = ElevenLabs(api_key=api_key)
            
            # Use the voice_id from your account with multilingual v2 model
            # Returns a generator that yields audio chunks
            audio_generator = client.text_to_speech.convert(
                voice_id="JBFqnCBsd6RMkjVDRZzb",  # Your voice ID
                text=text,
                model_id="eleven_multilingual_v2",  # Multilingual model
                output_format="mp3_44100_128",  # High quality
            )
            
            # Write the generator output to file
            with open(output_file, "wb") as f:
                for chunk in audio_generator:
                    f.write(chunk)
            
            print(f"Audio saved to {output_file}")
            return output_file
        except ImportError:
            raise ImportError("elevenlabs not installed. Run: pip install elevenlabs")
        except Exception as e:
            raise RuntimeError(f"ElevenLabs TTS failed: {str(e)}")
            raise RuntimeError(f"ElevenLabs TTS failed: {str(e)}")

    def _tts_azure(self, text, output_file):
        """Use Azure Cognitive Services TTS."""
        try:
            import azure.cognitiveservices.speech as speechsdk
            
            speech_key = os.getenv("AZURE_SPEECH_KEY")
            service_region = os.getenv("AZURE_SPEECH_REGION", "eastus")
            
            if not speech_key:
                raise ValueError("AZURE_SPEECH_KEY not found in .env file")
            
            speech_config = speechsdk.SpeechConfig(
                subscription=speech_key,
                region=service_region
            )
            audio_config = speechsdk.audio.AudioOutputConfig(filename=output_file)
            
            synthesizer = speechsdk.SpeechSynthesizer(
                speech_config=speech_config,
                audio_config=audio_config
            )
            
            result = synthesizer.speak_text_async(text).get()
            
            if result.reason == speechsdk.ResultReason.SynthesizingSpeechCompleted:
                print(f"Audio saved to {output_file}")
                return output_file
            else:
                raise RuntimeError(f"TTS failed: {result.reason}")
        except ImportError:
            raise ImportError("azure-cognitiveservices-speech not installed. Run: pip install azure-cognitiveservices-speech")

    def play_audio(self, audio_file):
        """
        Play audio file using system default player.
        
        Args:
            audio_file: Path to audio file to play
        """
        try:
            if os.name == 'nt':  # Windows
                os.startfile(audio_file)
            elif os.name == 'posix':  # macOS/Linux
                subprocess.Popen(['open' if sys.platform == 'darwin' else 'xdg-open', audio_file])
            print(f"Playing {audio_file}")
        except Exception as e:
            print(f"Could not play audio: {e}")

    def answer_and_speak(self, query, context=None, output_file="response_audio.mp3"):
        """
        Generate an answer to a query and convert it to speech.
        
        Args:
            query: The question to answer
            context: Optional context
            output_file: Output audio file path
            
        Returns:
            Tuple of (answer_text, audio_file_path)
        """
        print("Generating answer...")
        answer = self.generate_answer(query, context)
        
        print("Converting to speech...")
        audio_file = self.text_to_speech(answer, output_file)
        
        print("Playing audio...")
        self.play_audio(audio_file)
        
        return answer, audio_file
