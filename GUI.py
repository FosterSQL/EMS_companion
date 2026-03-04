# gui.py
import tkinter as tk
from tkinter import scrolledtext, Toplevel
import threading
import os
import sys
import subprocess
import json
from dotenv import load_dotenv

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
if not API_KEY:
    raise ValueError("API_KEY not found in .env file")

class RecorderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Paramedic Voice Assistant")
        self.root.geometry("700x900")

        self.recorder = AudioRecorder()
        self.transcriber = Transcriber()
        self.extractor = ContextExtractor()
        self.form_filler = FormFiller()
        self.chatbot = ChatBot()
        self.answer_builder = AnswerBuilder(tts_engine="elevenlabs")
        self.conversation_manager = ConversationManager()
        self.form_session = FormSessionManager()
        self.schedule_manager = ScheduleManager()
        self.shift_change_manager = ShiftChangeManager()
        self.checklist_manager = ChecklistManager()

        self.is_recording = False
        self.last_transcription = ""
        self.form_completion_mode = False
        self.current_form_name = ""
        self.current_form_data = {}
        self.unknown_fields = []

        # ----- Top buttons -----
        btn_frame = tk.Frame(root)
        btn_frame.pack(pady=10)

        self.record_btn = tk.Button(
            btn_frame,
            text="🎤 Record",
            font=("Arial", 16),
            width=8,
            bg="lightblue",
            command=self.toggle_recording
        )
        self.record_btn.pack(side=tk.LEFT, padx=5)

        self.fill_btn = tk.Button(
            btn_frame,
            text="📝 Fill Form",
            font=("Arial", 16),
            width=8,
            bg="lightgreen",
            state=tk.DISABLED,
            command=self.open_form_window
        )
        self.fill_btn.pack(side=tk.LEFT, padx=5)

        # ----- Main text area -----
        self.text_area = scrolledtext.ScrolledText(
            root,
            wrap=tk.WORD,
            width=80,
            height=20,
            font=("Arial", 10)
        )
        self.text_area.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

    # ----- Recording methods -----
    def toggle_recording(self):
        if not self.is_recording:
            self.is_recording = True
            self.record_btn.config(text="⏹ Stop", bg="lightcoral")
            self.text_area.delete(1.0, tk.END)
            self.text_area.insert(tk.END, "Recording... Speak now.")
            threading.Thread(target=self.recorder.start_recording, daemon=True).start()
        else:
            self.is_recording = False
            self.record_btn.config(text="🎤 Record", bg="lightblue")
            self.text_area.insert(tk.END, "\n\nStopping recording... transcribing...")
            self.recorder.stop_recording("output.wav")
            threading.Thread(target=self.transcribe_audio, daemon=True).start()

    def load_recent_context(self, max_entries=3):
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

    def transcribe_audio(self):
        try:
            past_context = self.load_recent_context()
            text = self.transcriber.transcribe(
                "output.wav",
                past_context=past_context,
                output_path="response.txt"
            )
            self.last_transcription = text

            data = self.extractor.extract(text, output_path="context.json")

            display = "📝 TRANSCRIPTION:\n" + text + "\n\n📊 EXTRACTED INFO:\n"
            for k, v in data.items():
                display += f"{k}: {v}\n"

            self.root.after(0, self.display_transcription, display)
            self.root.after(0, lambda: self.fill_btn.config(state=tk.NORMAL))
            
            # Automatically generate AI response and speak it
            self.root.after(0, self.display_transcription, display + "\n\n🤖 Generating AI response...")
            threading.Thread(target=self.auto_generate_and_speak, args=(text, past_context), daemon=True).start()
            
        except Exception as e:
            self.root.after(0, self.display_error, str(e))
    
    def auto_generate_and_speak(self, transcription, context):
        """Generate AI response to transcription and speak it automatically."""
        try:
            # Display transcription
            display = f"TRANSCRIPTION:\n{transcription}\n\n"
            self.root.after(0, self.display_transcription, display + "Analyzing...")
            
            # Check for shift change request first (has its own session)
            if self.shift_change_manager.active_session or self.shift_change_manager.is_shift_change_request(transcription):
                scr_result = self.shift_change_manager.process_message(transcription)
                action = scr_result["action"]
                
                if action == "start_scr":
                    display += "SHIFT CHANGE REQUEST DETECTED\n\n"
                    if scr_result["extracted"]:
                        display += "CAPTURED:\n"
                        for field, value in scr_result["extracted"].items():
                            display += f"  - {field.replace('_', ' ').title()}: {value}\n"
                        display += "\n"
                    
                    if scr_result["is_complete"]:
                        reply = "Got all the info! Ready to submit your shift change request. Say 'submit' to confirm."
                    else:
                        reply = scr_result["next_question"] or "What details can you give me?"
                        display += f"STILL NEEDED: {', '.join([f.replace('_', ' ') for f in scr_result['missing']])}\n\n"
                
                elif action == "update_scr":
                    display += "SHIFT CHANGE REQUEST\n\n"
                    if scr_result["extracted"]:
                        display += "NEW INFO:\n"
                        for field, value in scr_result["extracted"].items():
                            display += f"  - {field.replace('_', ' ').title()}: {value}\n"
                        display += "\n"
                    
                    display += "COLLECTED SO FAR:\n"
                    for field, value in scr_result["collected"].items():
                        display += f"  - {field.replace('_', ' ').title()}: {value}\n"
                    display += "\n"
                    
                    if scr_result["missing"]:
                        display += f"STILL NEEDED: {', '.join([f.replace('_', ' ') for f in scr_result['missing']])}\n\n"
                        reply = scr_result["next_question"]
                    else:
                        reply = "Got everything! Say 'submit' to send your shift change request."
                
                elif action == "complete_scr":
                    display += "SHIFT CHANGE REQUEST COMPLETE\n\n"
                    for field, value in scr_result["collected"].items():
                        display += f"  - {field.replace('_', ' ').title()}: {value}\n"
                    
                    # Check if user wants to submit
                    if "submit" in transcription.lower() or "send" in transcription.lower() or "confirm" in transcription.lower():
                        success, msg = self.shift_change_manager.submit_form()
                        reply = msg
                        display += f"\n{msg}\n"
                    else:
                        reply = "Ready to submit! Say 'submit' or 'send' to confirm your shift change request."
                
                else:
                    # Check if user says submit while session is active
                    if self.shift_change_manager.active_session and ("submit" in transcription.lower() or "send" in transcription.lower()):
                        if self.shift_change_manager.is_complete():
                            success, msg = self.shift_change_manager.submit_form()
                            reply = msg
                            display += f"\n{msg}\n"
                        else:
                            missing = self.shift_change_manager.get_missing_fields()
                            reply = f"Can't submit yet, still need: {', '.join([f.replace('_', ' ') for f in missing])}"
                    else:
                        reply = "I didn't catch that. What shift change details do you have?"
                
                display += f"RESPONSE:\n{reply}"
            
            # Check if this is a schedule-related query
            elif self.schedule_manager.is_schedule_query(transcription):
                display += "SCHEDULE QUERY DETECTED\n\n"
                self.root.after(0, self.display_transcription, display + "Fetching schedule data...")
                
                # Fetch real-time schedule and answer
                reply = self.schedule_manager.answer_schedule_query(transcription)
                display += f"RESPONSE:\n{reply}"
            
            # Check for daily checklist
            elif self.checklist_manager.active_session or self.checklist_manager.is_checklist_request(transcription):
                cl_result = self.checklist_manager.process_message(transcription)
                action = cl_result["action"]
                
                if action == "start_checklist":
                    display += "DAILY CHECKLIST STARTED\n\n"
                    display += f"Items to check: {len(cl_result['remaining'])}\n\n"
                    reply = cl_result["next_prompt"]
                
                elif action == "update_checklist":
                    display += "CHECKLIST UPDATE\n\n"
                    if cl_result["updated"]:
                        display += "JUST UPDATED:\n"
                        for code in cl_result["updated"]:
                            status = cl_result["completed"][code]
                            item_type = self.checklist_manager.CHECKLIST_ITEMS[code]["type"]
                            icon = "OK" if status["status"] == "good" else "ISSUE"
                            display += f"  [{icon}] {item_type}\n"
                        display += "\n"
                    
                    display += f"Progress: {len(cl_result['completed'])}/{len(self.checklist_manager.CHECKLIST_ITEMS)} items\n"
                    if cl_result["remaining"]:
                        display += f"Remaining: {len(cl_result['remaining'])}\n\n"
                    
                    reply = cl_result["next_prompt"]
                
                elif action == "complete_checklist":
                    display += "CHECKLIST COMPLETE!\n\n"
                    display += self.checklist_manager.get_summary()
                    
                    if cl_result["issues"]:
                        reply = f"All checked! You have {len(cl_result['issues'])} item(s) needing attention."
                    else:
                        reply = "All done! Everything looks good. Ready to start your shift!"
                    
                    # Save checklist
                    filepath = self.checklist_manager.export_checklist()
                    display += f"\nSaved to: {filepath}\n"
                    self.checklist_manager.end_session()
                
                elif action == "no_match":
                    reply = cl_result["next_prompt"]
                
                else:
                    reply = "Tell me about any checklist item - like your ACRs, vaccinations, uniform, or overtime."
                
                display += f"RESPONSE:\n{reply}"
                
            else:
                # Process through form session manager
                form_result = self.form_session.process_message(transcription)
                action = form_result["action"]
            
                # Handle form-related actions
                if action == "start_form":
                    display += f"FORM DETECTED: {form_result['form_name']}\n\n"
                    if form_result["extracted"]:
                        display += "CAPTURED:\n"
                        for field, value in form_result["extracted"].items():
                            display += f"  - {field.replace('_', ' ').title()}: {value}\n"
                        display += "\n"
                    
                    if form_result["is_complete"]:
                        reply = f"Got it! Your {form_result['form_name']} is complete. Ready to submit."
                    else:
                        reply = form_result["next_question"] or "What other details can you provide?"
                        missing = form_result["missing"]
                        display += f"STILL NEEDED: {', '.join([f.replace('_', ' ') for f in missing])}\n\n"
                    
                elif action == "update_form":
                    display += f"FORM: {form_result['form_name']}\n\n"
                    if form_result["extracted"]:
                        display += "NEW INFO CAPTURED:\n"
                        for field, value in form_result["extracted"].items():
                            display += f"  - {field.replace('_', ' ').title()}: {value}\n"
                        display += "\n"
                    
                    # Show all collected so far
                    display += "ALL COLLECTED:\n"
                    for field, value in form_result["collected"].items():
                        display += f"  - {field.replace('_', ' ').title()}: {value}\n"
                    display += "\n"
                    
                    missing = form_result["missing"]
                    if missing:
                        display += f"STILL NEEDED: {', '.join([f.replace('_', ' ') for f in missing])}\n\n"
                        reply = form_result["next_question"] or f"I still need the {missing[0].replace('_', ' ')}."
                    else:
                        reply = "Form is complete!"
                    
                elif action == "complete_form":
                    display += f"FORM COMPLETE: {form_result['form_name']}\n\n"
                    display += "ALL FIELDS:\n"
                    for field, value in form_result["collected"].items():
                        display += f"  - {field.replace('_', ' ').title()}: {value}\n"
                    display += "\n"
                    
                    reply = f"Perfect! Your {form_result['form_name']} is complete with all fields filled. Would you like to submit it?"
                    
                    # Store completed form data for the Fill Form button
                    self.current_form_name = form_result["form_name"]
                    self.current_form_data = form_result["collected"]
                    self.root.after(0, lambda: self.fill_btn.config(state=tk.NORMAL))
                    
                else:
                    # No form intent - regular conversation
                    analysis = self.conversation_manager.add_message(transcription)
                    intent = analysis["intent"]
                    details = analysis["details"]
                    
                    display += f"INTENT: {intent}\n\n"
                    if details:
                        display += "DETAILS:\n"
                        for category, value in details.items():
                            if value and value is not None:
                                display += f"  - {category}: {value}\n"
                        display += "\n"
                    
                    # Generate conversational response
                    prompt = f"Respond in ONE short sentence to your colleague: {transcription}"
                    reply = self.answer_builder.generate_answer(prompt, context)
                    
                    self.conversation_manager.conversation_history.append({
                        "role": "assistant",
                        "content": reply
                    })
                    
                    # Display the response  
                    display += f"RESPONSE:\n{reply}"
            
            # Display the response and generate audio
            self.root.after(0, self.display_transcription, display + "\n\nGenerating audio...")
            
            # Convert to speech and play
            audio_file = self.answer_builder.text_to_speech(
                reply,
                output_file="assistant_response.mp3"
            )
            
            self.root.after(0, self.display_transcription, display + "\n\nPlaying audio...")
            
            if sys.platform == "win32":
                os.startfile(audio_file)
            elif sys.platform == "darwin":
                subprocess.run(["afplay", audio_file])
            else:
                subprocess.run(["paplay", audio_file])
            
            # Show form status if in session
            if self.form_session.active_session:
                display += "\n\n" + self.form_session.get_form_summary()
            
            display += "\n\nReady for next recording."
            self.root.after(0, self.display_transcription, display)
            
        except Exception as e:
            self.root.after(0, self.display_error, f"Response generation error: {str(e)}")

    def display_transcription(self, text):
        self.text_area.delete(1.0, tk.END)
        self.text_area.insert(tk.END, text)

    def display_error(self, msg):
        self.text_area.delete(1.0, tk.END)
        self.text_area.insert(tk.END, f"Error: {msg}")

    # ----- Form filling and chat integration -----
    def open_form_window(self):
        if not self.last_transcription:
            return
        threading.Thread(target=self.fill_form_and_show, daemon=True).start()

    def fill_form_and_show(self):
        try:
            form_name, filled_data = self.form_filler.process(self.last_transcription)
            self.current_form_name = form_name
            self.current_form_data = filled_data
            self.unknown_fields = [f for f, v in filled_data.items() if v == "unknown"]
            self.root.after(0, self.display_form_and_ask)
            self.root.after(0, self.create_form_display_window, form_name, filled_data)
        except Exception as e:
            self.root.after(0, self.display_error, f"Form filling error: {str(e)}")

    def display_form_and_ask(self):
        display = f"Filled Form: {self.current_form_name}\n\n"
        for field, value in self.current_form_data.items():
            display += f"{field.replace('_', ' ').title()}: {value}\n"
        self.text_area.delete(1.0, tk.END)
        self.text_area.insert(tk.END, display)

        if self.unknown_fields:
            self.form_completion_mode = True
            display += f"\n⚠️ Still need: {', '.join(self.unknown_fields)}\nRecord info for missing fields."
            self.text_area.delete(1.0, tk.END)
            self.text_area.insert(tk.END, display)
        else:
            self.form_completion_mode = False

    def update_form_display(self):
        display = f"Filled Form: {self.current_form_name}\n\n"
        for field, value in self.current_form_data.items():
            display += f"{field.replace('_', ' ').title()}: {value}\n"
        self.text_area.delete(1.0, tk.END)
        self.text_area.insert(tk.END, display)

    # ----- Email feature -----
    def confirm_and_send_email(self, form_name, form_data):
        """Show confirmation dialog and send email via SMTP."""
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        from datetime import datetime

        smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        smtp_port = int(os.getenv("SMTP_PORT", 587))
        sender_email = os.getenv("SENDER_EMAIL")
        sender_password = os.getenv("SENDER_PASSWORD")

        win = Toplevel(self.root)
        win.title("Confirm Email")
        win.geometry("600x500")

        text = scrolledtext.ScrolledText(win, wrap=tk.WORD, width=70, height=20)
        text.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        recipient = "Team00@EffectiveAI.net"
        subject = f"{form_name} - {form_data.get('reported_by_name', 'Paramedic')}"
        body = f"Form: {form_name}\n\n"
        for field, value in form_data.items():
            body += f"{field.replace('_', ' ').title()}: {value}\n"

        email_content = f"To: {recipient}\nSubject: {subject}\n\n{body}"
        text.insert(tk.END, email_content)
        text.config(state=tk.DISABLED)

        btn_frame = tk.Frame(win)
        btn_frame.pack(pady=10)

        def send_email():
            send_btn.config(state=tk.DISABLED, text="Sending...")
            win.update()

            try:
                if not sender_email or not sender_password:
                    filename = f"{form_name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                    with open(filename, 'w') as f:
                        f.write(email_content)
                    self.add_chat_message("System", f"⚠️ No email credentials. Form saved as {filename}")
                    win.destroy()
                    return

                msg = MIMEMultipart()
                msg['From'] = sender_email
                msg['To'] = recipient
                msg['Subject'] = subject
                msg.attach(MIMEText(body, 'plain'))

                with smtplib.SMTP(smtp_server, smtp_port) as server:
                    server.starttls()
                    server.login(sender_email, sender_password)
                    server.send_message(msg)

                self.add_chat_message("System", f"✅ Email successfully sent to {recipient}")
            except Exception as e:
                self.add_chat_message("System", f"❌ Failed to send email: {str(e)}")
            finally:
                win.destroy()

        send_btn = tk.Button(btn_frame, text="Send Email", command=send_email, bg="lightgreen")
        send_btn.pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Cancel", command=win.destroy, bg="lightcoral").pack(side=tk.LEFT, padx=5)

    def create_form_display_window(self, form_name, filled_data):
        """Pop-up window with the filled form and email button."""
        win = Toplevel(self.root)
        win.title(f"Filled Form: {form_name}")
        win.geometry("600x600")

        text = scrolledtext.ScrolledText(win, wrap=tk.WORD, width=70, height=25)
        text.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        content = f"Form: {form_name}\n\n"
        for field, value in filled_data.items():
            content += f"{field.replace('_', ' ').title()}: {value}\n"
        text.insert(tk.END, content)
        text.config(state=tk.DISABLED)

        tk.Button(
            win,
            text="📧 Send via Email",
            command=lambda: self.confirm_and_send_email(form_name, filled_data),
            bg="lightblue",
            font=("Arial", 12)
        ).pack(pady=10)

if __name__ == "__main__":
    root = tk.Tk()
    app = RecorderApp(root)
    root.mainloop()