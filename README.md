# Paramedic Voice Assistant

An AI-powered voice assistant designed for paramedics to streamline documentation and workflow through natural voice interactions.

## Features

- **🎤 Voice Recording**: Record audio inputs directly from the interface
- **📝 Accurate Transcription**:Verbatim speech-to-text using OpenAI's GPT-4o Audio model
- **🤖 AI Assistant**: Context-aware responses with conversation memory
- **🔊 Voice Output**: Premium text-to-speech using ElevenLabs
- **📋 Auto Form Filling**: Intelligent form selection and completion
- **📧 Email Integration**: Send completed forms via email

## Technologies

- **Frontend**: Python Tkinter GUI
- **Audio**: PyAudio for recording
- **AI Models**: OpenRouter API (OpenAI GPT-4o)
- **Voice**: ElevenLabs TTS (Multilingual v2)
- **Context Management**: JSON-based conversation history

## Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd hackathon_project_V2
   ```

2. **Create virtual environment**
   ```bash
   python -m venv .venv
   .venv\Scripts\activate  # Windows
   ```

3. **Install dependencies**
   ```bash
   pip install openai python-dotenv elevenlabs pyaudio edge-tts
   ```

4. **Configure environment variables**
   Create a `.env` file:
   ```
   API_KEY=your_openrouter_api_key
   ELEVENLABS_API_KEY=your_elevenlabs_api_key
   SENDER_EMAIL=your_email@gmail.com
   SENDER_PASSWORD=your_app_password
   SMTP_SERVER=smtp.gmail.com
   SMTP_PORT=587
   ```

5. **Run the application**
   ```bash
   python GUI.py
   ```

## Usage

1. Click **🎤 Record** to start recording
2. Speak your message/query
3. Click **⏹ Stop** to end recording
4. The assistant will:
   - Transcribe your speech
   - Generate a contextual response
   - Speak the response using premium voice
5. Use **📝 Fill Form** to auto-complete paramedic forms

## Project Structure

```
.
├── GUI.py                  # Main application interface
├── AudioRecorder.py        # Audio recording functionality
├── Transcriber.py          # Speech-to-text conversion
├── AnswerBuilder.py        # AI response generation & TTS
├── ContextExtractor.py     # Extract structured data from text
├── FormFiller.py           # Automatic form completion
├── ChatBot.py              # Conversational AI logic
├── forms.py                # Form templates
├── FreeMp3.py              # Alternative TTS implementation
└── .env                    # Environment configuration (not tracked)
```

## Forms Supported

- Occurrence Report
- Teddy Bear Tracking
- Shift Log
- Equipment Request

## License

This project was created for a hackathon.

## Contributors

- Team 00 @ EffectiveAI.net
