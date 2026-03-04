# Flask web server for Paramedic Voice Assistant
import os
import sys
import json
import threading
import subprocess
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file
from dotenv import load_dotenv

# Import existing managers
from AudioRecorder import AudioRecorder
from Transcriber import Transcriber
from ContextExtractor import ContextExtractor
from FormFiller import FormFiller
from ChatBot import ChatBot
from AnswerBuilder import AnswerBuilder
from ConversationManager import ConversationManager
from FormSessionManager import FormSessionManager
from ScheduleManager import ScheduleManager
from ShiftChangeManager import ShiftChangeManager
from ChecklistManager import ChecklistManager

load_dotenv()
API_KEY = os.getenv("API_KEY")

app = Flask(__name__, static_folder='static', template_folder='templates')

# Initialize all managers
recorder = AudioRecorder()
transcriber = Transcriber()
extractor = ContextExtractor()
form_filler = FormFiller()
chatbot = ChatBot()
answer_builder = AnswerBuilder(tts_engine="elevenlabs")
conversation_manager = ConversationManager()
form_session = FormSessionManager()
schedule_manager = ScheduleManager()
shift_change_manager = ShiftChangeManager()
checklist_manager = ChecklistManager()


def load_recent_context(max_entries=3):
    if not os.path.exists("context.json"):
        return None
    with open("context.json", "r", encoding="utf-8") as f:
        entries = json.load(f)
    recent = entries[-max_entries:] if entries else []
    if not recent:
        return None
    lines = ["Recent incidents:"]
    for i, e in enumerate(recent, 1):
        desc = e.get('brief_description', 'No description')
        when = e.get('when', 'unknown')
        where = e.get('where', 'unknown')
        lines.append(f"{i}. [{when} at {where}] {desc}")
    return "\n".join(lines)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/process', methods=['POST'])
def process_message():
    """Process a text message and return AI response."""
    data = request.json
    message = data.get('message', '')
    
    if not message:
        return jsonify({'error': 'No message provided'}), 400
    
    result = {
        'type': 'conversation',
        'response': '',
        'display': '',
        'data': None,
        'show_preview': False
    }
    
    past_context = load_recent_context()
    
    # Check for shift change request
    if shift_change_manager.active_session or shift_change_manager.is_shift_change_request(message):
        scr_result = shift_change_manager.process_message(message)
        action = scr_result["action"]
        result['type'] = 'shift_change'
        
        if action in ["start_scr", "update_scr"]:
            result['data'] = {
                'collected': scr_result['collected'],
                'missing': scr_result['missing'],
                'is_complete': scr_result['is_complete']
            }
            
            if scr_result['is_complete']:
                result['response'] = "Got all the info! Here's your shift change request. Ready to submit?"
                result['show_preview'] = True
            else:
                result['response'] = scr_result['next_question'] or "What else can you tell me?"
        
        elif action == "complete_scr":
            result['data'] = {'collected': scr_result['collected']}
            result['response'] = "Your shift change request is ready. Would you like to submit it?"
            result['show_preview'] = True
    
    # Check for schedule query
    elif schedule_manager.is_schedule_query(message):
        result['type'] = 'schedule'
        result['response'] = schedule_manager.answer_schedule_query(message)
    
    # Check for checklist
    elif checklist_manager.active_session or checklist_manager.is_checklist_request(message):
        cl_result = checklist_manager.process_message(message)
        action = cl_result["action"]
        result['type'] = 'checklist'
        
        if action == "start_checklist":
            result['data'] = {
                'completed': cl_result['completed'],
                'remaining': cl_result['remaining'],
                'issues': cl_result['issues']
            }
            result['response'] = cl_result['next_prompt']
        
        elif action == "update_checklist":
            result['data'] = {
                'completed': cl_result['completed'],
                'remaining': cl_result['remaining'],
                'issues': cl_result['issues'],
                'updated': cl_result.get('updated', [])
            }
            result['response'] = cl_result['next_prompt']
        
        elif action == "complete_checklist":
            result['data'] = {
                'completed': cl_result['completed'],
                'issues': cl_result['issues'],
                'summary': checklist_manager.get_summary()
            }
            result['response'] = "All done! Here's your checklist summary."
            result['show_preview'] = True
            
            # Save checklist
            checklist_manager.export_checklist()
            checklist_manager.end_session()
        
        else:
            result['response'] = cl_result.get('next_prompt', "Tell me about any checklist item.")
    
    # Check for form-related
    else:
        form_result = form_session.process_message(message)
        action = form_result["action"]
        
        if action in ["start_form", "update_form"]:
            result['type'] = 'form'
            result['data'] = {
                'form_name': form_result['form_name'],
                'collected': form_result['collected'],
                'missing': form_result['missing'],
                'is_complete': form_result['is_complete']
            }
            
            if form_result['is_complete']:
                result['response'] = f"Your {form_result['form_name']} is complete! Ready to submit?"
                result['show_preview'] = True
            else:
                result['response'] = form_result['next_question'] or f"I still need: {', '.join(form_result['missing'])}"
        
        elif action == "complete_form":
            result['type'] = 'form'
            result['data'] = {
                'form_name': form_result['form_name'],
                'collected': form_result['collected']
            }
            result['response'] = f"Your {form_result['form_name']} is ready! Review and submit when ready."
            result['show_preview'] = True
        
        else:
            # Regular conversation
            analysis = conversation_manager.add_message(message)
            prompt = f"Respond in ONE short sentence to your colleague: {message}"
            result['response'] = answer_builder.generate_answer(prompt, past_context)
            conversation_manager.conversation_history.append({
                "role": "assistant",
                "content": result['response']
            })
    
    return jsonify(result)


@app.route('/api/transcribe', methods=['POST'])
def transcribe_audio():
    """Transcribe uploaded audio file."""
    if 'audio' not in request.files:
        return jsonify({'error': 'No audio file'}), 400
    
    audio_file = request.files['audio']
    filename = audio_file.filename or 'recording.webm'
    
    # Determine format from filename or content type
    content_type = audio_file.content_type or ''
    if 'webm' in filename or 'webm' in content_type:
        temp_input = "temp_recording.webm"
    elif 'mp4' in filename or 'm4a' in filename or 'mp4' in content_type:
        temp_input = "temp_recording.mp4"
    elif 'ogg' in filename or 'ogg' in content_type:
        temp_input = "temp_recording.ogg"
    else:
        temp_input = "temp_recording.webm"
    
    temp_wav = "temp_recording.wav"
    audio_file.save(temp_input)
    
    print(f"Received audio: {filename}, content-type: {content_type}")
    
    try:
        # Get ffmpeg path from imageio-ffmpeg
        import imageio_ffmpeg
        ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
        
        # Convert to wav using ffmpeg directly via subprocess
        import subprocess
        result = subprocess.run([
            ffmpeg_path,
            '-y',  # Overwrite output
            '-i', temp_input,  # Input file
            '-ar', '16000',  # Sample rate
            '-ac', '1',  # Mono
            '-f', 'wav',  # Output format
            temp_wav
        ], capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"FFmpeg error: {result.stderr}")
            return jsonify({'error': f'Audio conversion failed: {result.stderr}'}), 500
        
        past_context = load_recent_context()
        text = transcriber.transcribe(temp_wav, past_context=past_context)
        
        # Extract context
        data = extractor.extract(text, output_path="context.json")
        
        return jsonify({
            'transcription': text,
            'extracted': data
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        if os.path.exists(temp_input):
            os.remove(temp_input)
        if os.path.exists(temp_wav):
            os.remove(temp_wav)


@app.route('/api/speak', methods=['POST'])
def text_to_speech():
    """Convert text to speech and return audio file."""
    data = request.json
    text = data.get('text', '')
    
    if not text:
        return jsonify({'error': 'No text provided'}), 400
    
    try:
        audio_file = answer_builder.text_to_speech(text, output_file="assistant_response.mp3")
        return send_file(audio_file, mimetype='audio/mpeg')
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/submit/shift-change', methods=['POST'])
def submit_shift_change():
    """Submit shift change request."""
    try:
        success, msg = shift_change_manager.submit_form()
        shift_change_manager.reset()
        return jsonify({'success': success, 'message': msg})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/submit/checklist', methods=['POST'])
def submit_checklist():
    """Submit completed checklist."""
    try:
        filepath = checklist_manager.export_checklist()
        checklist_manager.end_session()
        return jsonify({'success': True, 'message': 'Checklist submitted successfully!', 'file': filepath})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/submit/form', methods=['POST'])
def submit_form():
    """Submit form data."""
    data = request.json
    form_name = data.get('form_name', 'Form')
    form_data = data.get('data', {})
    
    try:
        # Save to file
        filename = f"{form_name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w') as f:
            json.dump(form_data, f, indent=2)
        
        form_session.reset_session()
        return jsonify({'success': True, 'message': f'{form_name} submitted successfully!', 'file': filename})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/reset', methods=['POST'])
def reset_session():
    """Reset all sessions to start fresh."""
    data = request.json
    session_type = data.get('type', 'all')
    
    if session_type in ['shift_change', 'all']:
        shift_change_manager.reset()
    if session_type in ['checklist', 'all']:
        checklist_manager.end_session()
    if session_type in ['form', 'all']:
        form_session.reset_session()
    if session_type in ['conversation', 'all']:
        conversation_manager.reset()
    
    return jsonify({'success': True})


@app.route('/api/checklist/items', methods=['GET'])
def get_checklist_items():
    """Get all checklist items for display."""
    items = []
    for code, info in checklist_manager.CHECKLIST_ITEMS.items():
        status = checklist_manager.completed_items.get(code, {})
        items.append({
            'code': code,
            'type': info['type'],
            'description': info['description'],
            'status': status.get('status', 'pending'),
            'issues': status.get('issues', 0),
            'notes': status.get('notes', '')
        })
    return jsonify({
        'items': items,
        'active': checklist_manager.active_session
    })


if __name__ == '__main__':
    print("Starting Paramedic Voice Assistant Web Server...")
    print("Open http://localhost:5000 in your browser")
    app.run(debug=True, host='0.0.0.0', port=5000)
