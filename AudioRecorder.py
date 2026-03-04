# audio_recorder.py
import pyaudio
import wave
import threading
import time

class AudioRecorder:
    def __init__(self, format=pyaudio.paInt16, channels=1, rate=44100, chunk=1024):
        self.format = format
        self.channels = channels
        self.rate = rate
        self.chunk = chunk
        self.audio = pyaudio.PyAudio()
        self.frames = []
        self.recording = False
        self.thread = None
        self.stream = None

    def start_recording(self):
        """Start recording in a background thread."""
        if self.recording:
            return
        self.frames = []
        self.recording = True
        self.stream = self.audio.open(
            format=self.format,
            channels=self.channels,
            rate=self.rate,
            input=True,
            frames_per_buffer=self.chunk
        )
        self.thread = threading.Thread(target=self._record)
        self.thread.start()
        print("Recording started")

    def _record(self):
        while self.recording:
            data = self.stream.read(self.chunk)
            self.frames.append(data)

    def stop_recording(self, output_filename="output.wav"):
        """Stop recording, close stream, and save WAV file."""
        if not self.recording:
            return
        self.recording = False
        if self.thread:
            self.thread.join()
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        # Save to file
        wf = wave.open(output_filename, 'wb')
        wf.setnchannels(self.channels)
        wf.setsampwidth(self.audio.get_sample_size(self.format))
        wf.setframerate(self.rate)
        wf.writeframes(b''.join(self.frames))
        wf.close()
        print(f"Saved recording to {output_filename}")

    def __del__(self):
        self.audio.terminate()