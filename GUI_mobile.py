# Mobile-style GUI for Paramedic Voice Assistant
import tkinter as tk
from tkinter import font as tkfont
import threading
import os
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'  # Hide pygame welcome message
import sys
import subprocess
import json
import math
import time
import pygame
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

# Colors
COLORS = {
    'primary': '#1e40af',
    'primary_light': '#3b82f6',
    'success': '#16a34a',
    'danger': '#dc2626',
    'white': '#ffffff',
    'gray_100': '#f1f5f9',
    'gray_200': '#e2e8f0',
    'gray_600': '#475569',
    'gray_800': '#1e293b',
}


class AvatarCircle:
    """Animated avatar with pulse and ripple effects."""
    SIZE, BASE_R = 150, 45
    IDLE_COLOR, SPEAK_COLOR = "#6C63FF", "#9B59B6"
    RECORD_COLOR = "#dc2626"
    RIPPLE_COLORS = ["#6C63FF", "#8B7BFF", "#A99BFF"]

    def __init__(self, parent, bg):
        self.canvas = tk.Canvas(parent, width=self.SIZE, height=self.SIZE,
                                bg=bg, highlightthickness=0, cursor="hand2")
        self.cx = self.cy = self.SIZE // 2
        self._speaking = False
        self._recording = False
        self._phase = 0.0
        self._ripples = []
        self._anim_id = None
        r = self.BASE_R
        self._circle = self.canvas.create_oval(
            self.cx-r, self.cy-r, self.cx+r, self.cy+r,
            fill=self.IDLE_COLOR, outline="", width=0)
        gr = r + 6
        self._glow = self.canvas.create_oval(
            self.cx-gr, self.cy-gr, self.cx+gr, self.cy+gr,
            fill="", outline=self.IDLE_COLOR, width=2, dash=(4, 4))
        # Add mic icon in center
        self._icon = self.canvas.create_text(
            self.cx, self.cy, text="🎤", font=("Segoe UI Emoji", 28), fill="white")

    def pack(self, **kw):
        self.canvas.pack(**kw)

    def bind(self, event, callback):
        self.canvas.bind(event, callback)

    def start_speaking(self):
        if self._speaking or self._recording:
            return
        self._speaking = True
        self._phase = 0.0
        self._ripples.clear()
        self.canvas.itemconfig(self._icon, text="🔊")
        self._animate()

    def stop_speaking(self):
        self._speaking = False
        if self._anim_id and not self._recording:
            self.canvas.after_cancel(self._anim_id)
            self._anim_id = None
        if not self._recording:
            self._reset_circle()
        self.canvas.itemconfig(self._icon, text="🎤")

    def start_recording(self):
        if self._recording:
            return
        self._recording = True
        self._phase = 0.0
        self._ripples.clear()
        self.canvas.itemconfig(self._icon, text="⏹")
        self._animate_recording()

    def stop_recording(self):
        self._recording = False
        if self._anim_id:
            self.canvas.after_cancel(self._anim_id)
            self._anim_id = None
        self._reset_circle()
        self.canvas.itemconfig(self._icon, text="🎤")

    def _reset_circle(self):
        r = self.BASE_R
        self.canvas.coords(self._circle, self.cx-r, self.cy-r, self.cx+r, self.cy+r)
        self.canvas.itemconfig(self._circle, fill=self.IDLE_COLOR)
        gr = r + 6
        self.canvas.coords(self._glow, self.cx-gr, self.cy-gr, self.cx+gr, self.cy+gr)
        self.canvas.itemconfig(self._glow, outline=self.IDLE_COLOR, width=2)
        for rid, _ in self._ripples:
            self.canvas.delete(rid)
        self._ripples.clear()

    def _animate(self):
        if not self._speaking:
            return
        self._phase += 0.15
        pulse = 1.0 + 0.18 * math.sin(self._phase * 3)
        r = self.BASE_R * pulse
        self.canvas.coords(self._circle, self.cx-r, self.cy-r, self.cx+r, self.cy+r)
        t = (math.sin(self._phase * 2) + 1) / 2
        color = self._lerp(self.IDLE_COLOR, self.SPEAK_COLOR, t)
        self.canvas.itemconfig(self._circle, fill=color)
        gr = r + 6 + 4 * math.sin(self._phase * 2.5)
        self.canvas.coords(self._glow, self.cx-gr, self.cy-gr, self.cx+gr, self.cy+gr)
        self.canvas.itemconfig(self._glow, outline=color, width=1+int(2*(math.sin(self._phase*2)+1)))
        if int(self._phase * 10) % 12 == 0 and len(self._ripples) < 3:
            rr = r + 2
            rid = self.canvas.create_oval(self.cx-rr, self.cy-rr, self.cx+rr, self.cy+rr,
                                          fill="", outline=self.RIPPLE_COLORS[len(self._ripples)%3], width=2)
            self._ripples.append((rid, self._phase))
        alive = []
        for rid, birth in self._ripples:
            age = self._phase - birth
            if age > 2.5:
                self.canvas.delete(rid)
                continue
            ex = self.BASE_R + 18 * age
            self.canvas.coords(rid, self.cx-ex, self.cy-ex, self.cx+ex, self.cy+ex)
            self.canvas.itemconfig(rid, width=max(1, int(3-age)))
            alive.append((rid, birth))
        self._ripples = alive
        self._anim_id = self.canvas.after(33, self._animate)

    def _animate_recording(self):
        if not self._recording:
            return
        self._phase += 0.12
        pulse = 1.0 + 0.12 * math.sin(self._phase * 4)
        r = self.BASE_R * pulse
        self.canvas.coords(self._circle, self.cx-r, self.cy-r, self.cx+r, self.cy+r)
        t = (math.sin(self._phase * 3) + 1) / 2
        color = self._lerp(self.IDLE_COLOR, self.RECORD_COLOR, t)
        self.canvas.itemconfig(self._circle, fill=color)
        gr = r + 6 + 3 * math.sin(self._phase * 3)
        self.canvas.coords(self._glow, self.cx-gr, self.cy-gr, self.cx+gr, self.cy+gr)
        self.canvas.itemconfig(self._glow, outline=color, width=2)
        self._anim_id = self.canvas.after(33, self._animate_recording)

    @staticmethod
    def _lerp(c1, c2, t):
        r1, g1, b1 = int(c1[1:3],16), int(c1[3:5],16), int(c1[5:7],16)
        r2, g2, b2 = int(c2[1:3],16), int(c2[3:5],16), int(c2[5:7],16)
        return f"#{int(r1+(r2-r1)*t):02x}{int(g1+(g2-g1)*t):02x}{int(b1+(b2-b1)*t):02x}"


class FormPreviewWindow:
    """Professional form preview window matching EMS branding."""
    
    EMAIL_RECIPIENT = "Team00@EffectiveAI.net"
    
    # Form-specific configurations
    FORM_CONFIGS = {
        "Teddy Bear Tracking": {
            "title": "Teddy Bear Comfort Program",
            "subtitle": "Emergency Medical Services — Patient Comfort Tracking",
            "icon": "🧸",
            "color": "#1b5abd",
            "sections": [
                {"title": "Date & Time", "icon": "🕒", "fields": ["date"]},
                {"title": "Primary Medic", "icon": "👤", "fields": ["paramedic_name", "paramedic_id"]},
                {"title": "Teddy Bear Recipient", "icon": "💙", "fields": ["recipient_type", "gender", "location"]},
            ]
        },
        "Occurrence Report": {
            "title": "EMS Occurrence Report",
            "subtitle": "Emergency Medical Services — Incident Documentation",
            "icon": "📋",
            "color": "#1e3a5f",
            "sections": [
                {"title": "Incident Overview", "icon": "⚠️", "fields": ["incident_date", "incident_time", "location"]},
                {"title": "Description", "icon": "📝", "fields": ["description"]},
                {"title": "Reporter", "icon": "👤", "fields": ["reported_by_name", "reported_by_id", "supervisor_notified"]},
            ]
        },
        "Shift Change": {
            "title": "Shift Change Request",
            "subtitle": "EAI Ambulance Service — SCR Submission",
            "icon": "📅",
            "color": "#1d4ed8",
            "sections": [
                {"title": "Personal Info", "icon": "👤", "fields": ["first_name", "last_name", "medic_number"]},
                {"title": "Shift Details", "icon": "🕐", "fields": ["shift_date", "shift_start", "shift_end"]},
                {"title": "Request", "icon": "📝", "fields": ["reason", "requested_action"]},
            ]
        },
        "Shift Log": {
            "title": "Shift Log Entry",
            "subtitle": "Emergency Medical Services — Daily Log",
            "icon": "📓",
            "color": "#0369a1",
            "sections": [
                {"title": "Shift Details", "icon": "🕐", "fields": ["shift_date", "start_time", "end_time", "location"]},
                {"title": "Crew Info", "icon": "👥", "fields": ["partner_name"]},
                {"title": "Notes", "icon": "📝", "fields": ["notes"]},
            ]
        },
        "Equipment Request": {
            "title": "Equipment Request Form",
            "subtitle": "Emergency Medical Services — Supply Request",
            "icon": "🔧",
            "color": "#b45309",
            "sections": [
                {"title": "Request Details", "icon": "📦", "fields": ["item_name", "quantity", "reason"]},
                {"title": "Requester", "icon": "👤", "fields": ["requested_by", "date"]},
            ]
        },
    }

    def __init__(self, parent, form_name, form_data, on_submit=None, on_cancel=None):
        self.parent = parent
        self.form_name = form_name
        self.form_data = form_data
        self.on_submit = on_submit
        self.on_cancel = on_cancel
        
        # Get form config or use default
        self.config = self.FORM_CONFIGS.get(form_name, {
            "title": form_name,
            "subtitle": "Form Preview",
            "icon": "📄",
            "color": "#1e40af",
            "sections": [{"title": "Form Data", "icon": "📝", "fields": list(form_data.keys())}]
        })
        
        self.window = None
        self._create_window()
    
    def _create_window(self):
        """Create the form preview window."""
        self.window = tk.Toplevel(self.parent)
        self.window.title(self.config["title"])
        self.window.geometry("380x650")
        self.window.resizable(False, False)
        self.window.configure(bg="#f8fafc")
        
        # Center on parent
        x = self.parent.winfo_x() + (self.parent.winfo_width() - 380) // 2
        y = self.parent.winfo_y() + 50
        self.window.geometry(f"+{x}+{y}")
        self.window.transient(self.parent)
        self.window.grab_set()
        
        self._create_header()
        self._create_content()
        self._create_buttons()
    
    def _create_header(self):
        """Create the blue header with title."""
        header = tk.Frame(self.window, bg=self.config["color"], height=100)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        
        # Icon and stars
        icon_frame = tk.Frame(header, bg=self.config["color"])
        icon_frame.pack(pady=(15, 5))
        
        tk.Label(icon_frame, text="★", font=("Segoe UI", 10), bg=self.config["color"], fg="#93c5fd").pack(side=tk.LEFT, padx=5)
        tk.Label(icon_frame, text=self.config["icon"], font=("Segoe UI Emoji", 24), bg=self.config["color"]).pack(side=tk.LEFT)
        tk.Label(icon_frame, text="★", font=("Segoe UI", 10), bg=self.config["color"], fg="#93c5fd").pack(side=tk.LEFT, padx=5)
        
        # Title
        tk.Label(
            header,
            text=self.config["title"].upper(),
            font=("Segoe UI", 14, "bold"),
            bg=self.config["color"],
            fg="white"
        ).pack()
        
        # Subtitle
        tk.Label(
            header,
            text=self.config["subtitle"],
            font=("Segoe UI", 8),
            bg=self.config["color"],
            fg="#bfdbfe"
        ).pack(pady=(2, 0))
    
    def _create_content(self):
        """Create the scrollable content area with form sections."""
        # Container for scrollable content
        container = tk.Frame(self.window, bg="#f8fafc")
        container.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)
        
        # Canvas for scrolling
        canvas = tk.Canvas(container, bg="#f8fafc", highlightthickness=0)
        scrollbar = tk.Scrollbar(container, orient=tk.VERTICAL, command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg="#f8fafc")
        
        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor=tk.NW, width=365)
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        # scrollbar.pack(side=tk.RIGHT, fill=tk.Y)  # Hidden for cleaner look
        
        # Enable mouse wheel
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(-1 * (e.delta // 120), "units"))
        
        # Create sections
        for section in self.config["sections"]:
            self._create_section(scroll_frame, section)
    
    def _create_section(self, parent, section):
        """Create a form section with fields."""
        # Section container
        section_frame = tk.Frame(parent, bg="white", bd=1, relief=tk.SOLID)
        section_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Section header with blue background
        header = tk.Frame(section_frame, bg="#e8f1ff", height=30)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        
        header_content = tk.Frame(header, bg="#e8f1ff")
        header_content.pack(side=tk.LEFT, padx=10, pady=5)
        
        tk.Label(
            header_content,
            text=section["icon"],
            font=("Segoe UI Emoji", 12),
            bg="#e8f1ff"
        ).pack(side=tk.LEFT, padx=(0, 5))
        
        tk.Label(
            header_content,
            text=section["title"].upper(),
            font=("Segoe UI", 9, "bold"),
            bg="#e8f1ff",
            fg=self.config["color"]
        ).pack(side=tk.LEFT)
        
        # Fields
        fields_frame = tk.Frame(section_frame, bg="white")
        fields_frame.pack(fill=tk.X, padx=10, pady=10)
        
        for field in section["fields"]:
            self._create_field(fields_frame, field)
    
    def _create_field(self, parent, field_name):
        """Create a single field display."""
        field_frame = tk.Frame(parent, bg="white")
        field_frame.pack(fill=tk.X, pady=3)
        
        # Label (uppercase, small, gray)
        label_text = field_name.replace("_", " ").upper()
        tk.Label(
            field_frame,
            text=label_text,
            font=("Segoe UI", 8, "bold"),
            bg="white",
            fg="#9ca3af"
        ).pack(anchor=tk.W)
        
        # Value box
        value = self.form_data.get(field_name, "Not provided")
        if value is None:
            value = "Not provided"
        
        value_frame = tk.Frame(field_frame, bg="#f8fafc", bd=1, relief=tk.SOLID)
        value_frame.pack(fill=tk.X, pady=(2, 0))
        
        tk.Label(
            value_frame,
            text=str(value),
            font=("Segoe UI", 10),
            bg="#f8fafc",
            fg="#374151",
            anchor=tk.W,
            padx=10,
            pady=8
        ).pack(fill=tk.X)
    
    def _create_buttons(self):
        """Create the bottom action buttons."""
        btn_frame = tk.Frame(self.window, bg="white", height=70)
        btn_frame.pack(fill=tk.X, side=tk.BOTTOM)
        btn_frame.pack_propagate(False)
        
        # Separator line
        tk.Frame(btn_frame, bg="#e5e7eb", height=1).pack(fill=tk.X)
        
        # Buttons container
        btns = tk.Frame(btn_frame, bg="white")
        btns.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Edit button (to correct info)
        tk.Button(
            btns,
            text="EDIT",
            font=("Segoe UI", 9, "bold"),
            bg="#fef2f2",
            fg="#dc2626",
            activebackground="#fee2e2",
            relief=tk.FLAT,
            cursor="hand2",
            command=self._on_edit
        ).pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        # Submit button
        tk.Button(
            btns,
            text="SUBMIT RECORD",
            font=("Segoe UI", 9, "bold"),
            bg=self.config["color"],
            fg="white",
            activebackground="#1e3a5f",
            relief=tk.FLAT,
            cursor="hand2",
            command=self._on_submit
        ).pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
    
    def _on_edit(self):
        """Handle edit - close preview but keep session data for corrections."""
        self.window.destroy()
        if self.on_cancel:
            self.on_cancel()
    
    def _on_submit(self):
        """Handle form submission."""
        self.window.destroy()
        if self.on_submit:
            self.on_submit(self.form_name, self.form_data)
        else:
            # Default: show success popup
            self._show_success()
    
    def _show_success(self):
        """Show success popup."""
        success = tk.Toplevel(self.parent)
        success.title("Success")
        success.geometry("300x300")
        success.resizable(False, False)
        success.configure(bg="white")
        
        x = self.parent.winfo_x() + (self.parent.winfo_width() - 300) // 2
        y = self.parent.winfo_y() + 150
        success.geometry(f"+{x}+{y}")
        success.transient(self.parent)
        success.grab_set()
        
        # Green top border
        tk.Frame(success, bg="#16a34a", height=8).pack(fill=tk.X)
        
        # Icon
        tk.Label(success, text=self.config["icon"], font=("Segoe UI Emoji", 40), bg="white").pack(pady=(25, 10))
        
        # Title
        tk.Label(success, text="Record Submitted!", font=("Segoe UI", 16, "bold"), bg="white", fg="#1f2937").pack()
        
        # Message with email
        tk.Label(
            success,
            text=f"Your {self.form_name} has been\nsuccessfully sent to:",
            font=("Segoe UI", 10),
            bg="white",
            fg="#6b7280",
            justify=tk.CENTER
        ).pack(pady=(10, 2))
        
        # Email address highlighted
        tk.Label(
            success,
            text=self.EMAIL_RECIPIENT,
            font=("Segoe UI", 10, "bold"),
            bg="white",
            fg="#1d4ed8"
        ).pack()
        
        # Close button
        tk.Button(
            success,
            text="FINISH",
            font=("Segoe UI", 10, "bold"),
            bg=self.config["color"],
            fg="white",
            relief=tk.FLAT,
            width=20,
            cursor="hand2",
            command=success.destroy
        ).pack(pady=15)
        
        # Auto-close after 3 seconds
        success.after(3000, lambda: success.destroy() if success.winfo_exists() else None)


class MobileRecorderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Paramedic Assistant")
        
        # Phone-like dimensions
        self.window_width = 390
        self.window_height = 750
        
        # Center on screen
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        x = (screen_width - self.window_width) // 2
        y = (screen_height - self.window_height) // 2 - 50
        
        self.root.geometry(f"{self.window_width}x{self.window_height}+{x}+{y}")
        self.root.resizable(False, False)
        self.root.configure(bg=COLORS['primary'])
        
        # Initialize managers
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

        # Initialize pygame mixer for audio playback
        pygame.mixer.init()
        
        # State
        self.is_recording = False
        self.last_transcription = ""
        
        # Fonts
        self.font_big = tkfont.Font(family="Segoe UI", size=14)
        self.font_title = tkfont.Font(family="Segoe UI", size=18, weight="bold")
        
        # Build simple UI
        self.create_ui()

    def create_ui(self):
        """Create simplified UI with big logo and small chat."""
        
        # ===== TOP SECTION - Big Avatar =====
        top_frame = tk.Frame(self.root, bg=COLORS['primary'])
        top_frame.pack(fill=tk.BOTH, expand=True)
        
        # Animated avatar circle
        self.avatar = AvatarCircle(top_frame, COLORS['primary'])
        self.avatar.pack(expand=True)
        self.avatar.bind("<Button-1>", lambda e: self.toggle_recording())
        
        # Status text under avatar
        self.status_label = tk.Label(
            top_frame,
            text="Tap to speak",
            font=self.font_title,
            bg=COLORS['primary'],
            fg=COLORS['white']
        )
        self.status_label.pack(pady=(0, 20))

        # ===== CHAT BOX - Smaller with big font =====
        chat_container = tk.Frame(self.root, bg=COLORS['white'], height=200)
        chat_container.pack(fill=tk.X, padx=15, pady=10)
        chat_container.pack_propagate(False)
        
        # Scrollable text widget for chat
        self.chat_text = tk.Text(
            chat_container,
            font=self.font_big,
            bg=COLORS['white'],
            fg=COLORS['gray_800'],
            wrap=tk.WORD,
            height=8,
            relief=tk.FLAT,
            padx=10,
            pady=10
        )
        
        scrollbar = tk.Scrollbar(chat_container, command=self.chat_text.yview)
        self.chat_text.configure(yscrollcommand=scrollbar.set)
        
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.chat_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Configure text tags for styling
        self.chat_text.tag_configure("user", foreground=COLORS['primary'], font=(self.font_big.cget("family"), 14, "bold"))
        self.chat_text.tag_configure("ai", foreground=COLORS['gray_800'])
        self.chat_text.tag_configure("system", foreground=COLORS['gray_600'], font=(self.font_big.cget("family"), 12, "italic"))
        
        # Initial message
        self.chat_text.insert(tk.END, "🤖 ", "ai")
        self.chat_text.insert(tk.END, "Hey! I'm here to help. Just tap the circle whenever you're ready to chat.\n\n", "ai")
        self.chat_text.config(state=tk.DISABLED)

        # ===== BOTTOM - Input and mic button =====
        bottom_frame = tk.Frame(self.root, bg=COLORS['primary'])
        bottom_frame.pack(fill=tk.X, padx=15, pady=15)
        
        # Text input
        self.input_entry = tk.Entry(
            bottom_frame,
            font=self.font_big,
            bg=COLORS['white'],
            fg=COLORS['gray_800'],
            relief=tk.FLAT
        )
        self.input_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=10, padx=(0, 10))
        self.input_entry.bind("<Return>", self.send_text_message)
        
        # Mic button
        self.mic_btn = tk.Button(
            bottom_frame,
            text="🎤",
            font=("Segoe UI Emoji", 20),
            bg=COLORS['success'],
            fg=COLORS['white'],
            activebackground=COLORS['success'],
            relief=tk.FLAT,
            width=3,
            cursor="hand2",
            command=self.toggle_recording
        )
        self.mic_btn.pack(side=tk.RIGHT)

    def add_message(self, sender, text):
        """Add message to chat."""
        self.chat_text.config(state=tk.NORMAL)
        
        if sender == "user":
            self.chat_text.insert(tk.END, "You: ", "user")
            self.chat_text.insert(tk.END, f"{text}\n\n", "user")
        elif sender == "ai":
            self.chat_text.insert(tk.END, "🤖 ", "ai")
            self.chat_text.insert(tk.END, f"{text}\n\n", "ai")
        else:
            self.chat_text.insert(tk.END, f"⏳ {text}\n", "system")
        
        self.chat_text.config(state=tk.DISABLED)
        self.chat_text.see(tk.END)

    def clear_last_system_message(self):
        """Remove last system message."""
        self.chat_text.config(state=tk.NORMAL)
        content = self.chat_text.get("1.0", tk.END)
        lines = content.split('\n')
        
        # Find and remove last system message line
        for i in range(len(lines) - 1, -1, -1):
            if lines[i].startswith("⏳"):
                lines.pop(i)
                break
        
        self.chat_text.delete("1.0", tk.END)
        self.chat_text.insert("1.0", '\n'.join(lines))
        self.chat_text.config(state=tk.DISABLED)

    def toggle_recording(self):
        """Toggle audio recording."""
        if not self.is_recording:
            self.start_recording()
        else:
            self.stop_recording()

    def start_recording(self):
        self.is_recording = True
        self.mic_btn.config(bg=COLORS['danger'], text="⏹")
        self.status_label.config(text="🔴 Recording...")
        self.avatar.start_recording()
        self.add_message("system", "Recording... tap to stop")
        threading.Thread(target=self.recorder.start_recording, daemon=True).start()

    def stop_recording(self):
        self.is_recording = False
        self.mic_btn.config(bg=COLORS['success'], text="🎤")
        self.status_label.config(text="Processing...")
        self.avatar.stop_recording()
        self.recorder.stop_recording("output.wav")
        threading.Thread(target=self.transcribe_audio, daemon=True).start()

    def send_text_message(self, event=None):
        """Send typed message."""
        text = self.input_entry.get().strip()
        if text:
            self.input_entry.delete(0, tk.END)
            self.add_message("user", text)
            self.process_user_input(text)

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
        """Transcribe recorded audio."""
        try:
            self.root.after(0, lambda: self.add_message("system", "Transcribing..."))
            
            past_context = self.load_recent_context()
            text = self.transcriber.transcribe(
                "output.wav",
                past_context=past_context,
                output_path="response.txt"
            )
            
            self.root.after(0, self.clear_last_system_message)
            self.root.after(0, self.clear_last_system_message)  # Remove both system messages
            
            if text:
                self.last_transcription = text
                self.root.after(0, lambda: self.add_message("user", text))
                self.process_user_input(text)
            else:
                self.root.after(0, lambda: self.add_message("ai", "Sorry, couldn't hear that clearly. Mind trying again?"))
                self.root.after(0, self.reset_status)
            
        except Exception as e:
            self.root.after(0, lambda: self.add_message("ai", f"Error: {str(e)}"))
            self.root.after(0, self.reset_status)

    def reset_status(self):
        """Reset status to ready."""
        self.status_label.config(text="Tap to speak")

    def process_user_input(self, text):
        """Process user input and generate response."""
        threading.Thread(target=self._process_and_respond, args=(text,), daemon=True).start()

    def _process_and_respond(self, transcription):
        """Process input and generate AI response."""
        try:
            context = self.load_recent_context()
            reply = ""
            show_form_preview = False
            form_name = None
            form_data = None
            
            # Check for shift change request
            if self.shift_change_manager.active_session or self.shift_change_manager.is_shift_change_request(transcription):
                scr_result = self.shift_change_manager.process_message(transcription)
                
                if scr_result["is_complete"]:
                    reply = "Perfect, I've got everything! Let me show you a preview."
                    show_form_preview = True
                    form_name = "Shift Change"
                    form_data = scr_result["collected"]
                else:
                    reply = scr_result["next_question"] or "What else can you tell me about the shift?"
            
            # Check for schedule query
            elif self.schedule_manager.is_schedule_query(transcription):
                reply = self.schedule_manager.answer_schedule_query(transcription)
            
            # Check for checklist
            elif self.checklist_manager.active_session or self.checklist_manager.is_checklist_request(transcription):
                cl_result = self.checklist_manager.process_message(transcription)
                
                if cl_result["action"] == "complete_checklist":
                    self.checklist_manager.export_checklist()
                    reply = "Awesome, checklist done! All saved and ready to go."
                    self.checklist_manager.end_session()
                else:
                    reply = cl_result["next_prompt"]
            
            # Regular conversation
            else:
                form_result = self.form_session.process_message(transcription)
                
                if form_result["action"] in ["start_form", "update_form", "complete_form"]:
                    if form_result["is_complete"]:
                        reply = f"Great, your {form_result['form_name']} is ready! Let me show you a preview."
                        show_form_preview = True
                        form_name = form_result["form_name"]
                        form_data = form_result["collected"]
                    else:
                        reply = form_result["next_question"] or "What else can you tell me?"
                else:
                    analysis = self.conversation_manager.add_message(transcription)
                    prompt = f"Your paramedic colleague just said: '{transcription}'. Respond naturally like a supportive friend."
                    reply = self.answer_builder.generate_answer(prompt, context)
                    self.conversation_manager.conversation_history.append({
                        "role": "assistant",
                        "content": reply
                    })
            
            # Display response
            self.root.after(0, lambda: self.add_message("ai", reply))
            self.root.after(0, self.reset_status)
            
            # Start speaking animation
            self.root.after(0, self.avatar.start_speaking)
            
            # Speak the response using pygame (inline playback)
            audio_file = self.answer_builder.text_to_speech(reply, output_file="assistant_response.mp3")
            pygame.mixer.music.load(audio_file)
            pygame.mixer.music.play()
            
            # Wait for audio to finish while keeping animation running
            while pygame.mixer.music.get_busy():
                time.sleep(0.1)
            
            # Unload to release file lock for next TTS
            pygame.mixer.music.unload()
            
            self.root.after(0, self.avatar.stop_speaking)
            
            # Show form preview if form is complete
            if show_form_preview and form_name and form_data:
                self.root.after(100, lambda: self._show_form_preview(form_name, form_data))
                
        except Exception as e:
            self.root.after(0, lambda: self.add_message("ai", f"Error: {str(e)}"))
            self.root.after(0, self.reset_status)
            self.root.after(0, self.avatar.stop_speaking)

    def _show_form_preview(self, form_name, form_data):
        """Display form preview window."""
        def on_submit(name, data):
            # Save form data
            from datetime import datetime
            filename = f"{name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(filename, 'w') as f:
                json.dump(data, f, indent=2)
            
            # Send email to Team00@EffectiveAI.net
            try:
                self._send_form_email(name, data, FormPreviewWindow.EMAIL_RECIPIENT)
            except Exception as e:
                print(f"Email send failed: {e}")
            
            # Reset the appropriate session
            if "Shift" in name:
                self.shift_change_manager.end_session()
            else:
                self.form_session.end_session()
            
            self.add_message("ai", f"✅ {name} sent to {FormPreviewWindow.EMAIL_RECIPIENT}! What else can I help you with?")
        
        def on_cancel():
            # DON'T reset - keep session data so user can correct specific fields
            self.add_message("ai", "Sure! Which field do you want to correct? Just tell me the new value.")
        
        FormPreviewWindow(
            self.root,
            form_name,
            form_data,
            on_submit=on_submit,
            on_cancel=on_cancel
        )
    
    def _send_form_email(self, form_name, form_data, recipient):
        """Send form data via email."""
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        from datetime import datetime
        
        # SMTP Configuration
        SMTP_SERVER = "smtp.office365.com"
        SMTP_PORT = 587
        SENDER_EMAIL = "Team08@EffectiveAI.net"
        SENDER_PASSWORD = "Team08!"
        
        # Format form data as readable text
        lines = [f"{form_name} Submission", "=" * 40, f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ""]
        for field, value in form_data.items():
            lines.append(f"{field.replace('_', ' ').title()}: {value or 'N/A'}")
        
        body = "\n".join(lines)
        
        # Create message
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = recipient
        msg['Subject'] = f"[EMS Form] {form_name} - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        msg.attach(MIMEText(body, 'plain'))
        
        # Send email
        try:
            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                server.starttls()
                server.login(SENDER_EMAIL, SENDER_PASSWORD)
                server.send_message(msg)
            print(f"Email sent successfully to {recipient}")
        except Exception as e:
            print(f"Email send failed: {e}")
            # Save locally as backup
            email_file = f"email_{form_name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            with open(email_file, 'w') as f:
                f.write(f"To: {recipient}\n")
                f.write(f"From: {SENDER_EMAIL}\n")
                f.write(f"Subject: {msg['Subject']}\n\n")
                f.write(body)
            print(f"Email saved locally to {email_file}")
            raise


if __name__ == "__main__":
    root = tk.Tk()
    app = MobileRecorderApp(root)
    root.mainloop()
