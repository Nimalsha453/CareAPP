import os
import json
import threading
from datetime import datetime

# Define variables globally.
CONFIG_FILE = "user_session.json"
MODEL_FILE = "model.tflite"  # අලුත් TFLite Model එක!
LABELS_FILE = "labels.txt"

# Kivy Imports
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.clock import Clock
from kivy.uix.popup import Popup
from kivy.uix.textinput import TextInput
from kivy.uix.label import Label
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.graphics import Color, RoundedRectangle
from kivy.uix.camera import Camera
from kivy.utils import platform

# Specific try-except blocks so Android builds don't fail silently
try:
    import speech_recognition as sr
except: pass

try:
    import pyttsx3
except: pass

try:
    from plyer import notification
except: pass

try:
    import numpy as np
    from PIL import Image as PILImage
    import tflite_runtime.interpreter as tflite
except Exception as e:
    print("AI Libraries missing:", e)

# ... UI Components ...
class RoundedButton(Button):
    def __init__(self, **kwargs):
        self.btn_color = kwargs.pop('btn_color', (0.1, 0.4, 0.8, 1)) # Default Blue
        super(RoundedButton, self).__init__(**kwargs)
        self.background_normal = ''
        self.background_color = (0, 0, 0, 0)
        self.bind(pos=self.update_canvas, size=self.update_canvas)

    def update_canvas(self, *args):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(rgba=self.btn_color)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[18,])

# --- 1. LOGIN SCREEN ---
class LoginScreen(Screen):
    def __init__(self, **kwargs):
        super(LoginScreen, self).__init__(**kwargs)
        layout = BoxLayout(orientation='vertical', padding=40, spacing=15)
        layout.add_widget(Label(text="CARE APP", font_size=42, bold=True))
       
        self.username = TextInput(hint_text="Username (patient/caregiver)", multiline=False, size_hint_y=None, height=50)
        self.phone_input = TextInput(hint_text="Caregiver Mobile No", multiline=False, size_hint_y=None, height=50)
       
        login_btn = RoundedButton(text="LOG IN", font_size=20, bold=True, size_hint_y=None, height=60, btn_color=(0.1, 0.4, 0.8, 1))
        login_btn.bind(on_press=self.verify_and_save)
       
        layout.add_widget(self.username)
        layout.add_widget(self.phone_input)
        layout.add_widget(login_btn)
        self.add_widget(layout)

    def verify_and_save(self, instance):
        user = self.username.text.lower().strip()
        phone = self.phone_input.text.strip()
        if user and phone:
            with open(CONFIG_FILE, "w") as f:
                json.dump({"username": user, "phone": phone}, f)
            App.get_running_app().emergency_phone = phone
            self.manager.current = 'caregiver' if user == "caregiver" else 'patient'
        else:
            Popup(title="Error", content=Label(text="Please fill all fields"), size_hint=(0.6, 0.3)).open()

# --- 2. PATIENT DASHBOARD ---
class PatientScreen(Screen):
    def __init__(self, **kwargs):
        super(PatientScreen, self).__init__(**kwargs)
        layout = BoxLayout(orientation='vertical', padding=25, spacing=15)
       
        self.status_label = Label(text="Patient Dashboard", font_size=24, bold=True, size_hint_y=0.1)
        layout.add_widget(self.status_label)
       
        remind_box = BoxLayout(orientation='horizontal', spacing=10, size_hint_y=0.15)
        self.pat_med_name = TextInput(hint_text="Med Name", multiline=False)
        self.pat_time_in = TextInput(hint_text="HH:MM", multiline=False)
        add_rem_btn = RoundedButton(text="SET REMINDER", btn_color=(0.1, 0.4, 0.8, 1)) # Blue
        add_rem_btn.bind(on_press=self.add_patient_reminder)
        remind_box.add_widget(self.pat_med_name)
        remind_box.add_widget(self.pat_time_in)
        remind_box.add_widget(add_rem_btn)
        layout.add_widget(remind_box)

        self.voice_btn = RoundedButton(text="TALK TO ASSISTANT 🎙️", size_hint_y=0.15, btn_color=(0.1, 0.4, 0.8, 1)) # Blue
        self.voice_btn.bind(on_press=self.start_voice_assistant)
        layout.add_widget(self.voice_btn)

        med_btn = RoundedButton(text="I TOOK MY MEDICINE ✅", size_hint_y=0.15, btn_color=(0.1, 0.4, 0.8, 1)) # Blue
        med_btn.bind(on_press=self.confirm_med)
        layout.add_widget(med_btn)

        scan_btn = RoundedButton(text="SCAN MEDICINE (AI) 📷", size_hint_y=0.15, btn_color=(0.1, 0.4, 0.8, 1)) # Blue
        scan_btn.bind(on_press=self.start_scanner)
        layout.add_widget(scan_btn)

        emer_btn = RoundedButton(text="HELP / EMERGENCY 🚨", size_hint_y=0.2, font_size=24, bold=True, btn_color=(0.8, 0, 0, 1)) # Red
        emer_btn.bind(on_press=self.trigger_emergency)
        layout.add_widget(emer_btn)

        logout_btn = Button(text="Sign Out", size_hint_y=None, height=40, background_color=(0.3, 0.3, 0.3, 1))
        logout_btn.bind(on_press=lambda x: App.get_running_app().logout())
        layout.add_widget(logout_btn)

        self.add_widget(layout)
        Clock.schedule_interval(self.check_reminders, 30)

    # --- PATIENT LOGIC ---
    def start_scanner(self, instance):
        if not os.path.exists(MODEL_FILE):
            Popup(title="Warning!", content=Label(text=f"AI model '{MODEL_FILE}' not found!"), size_hint=(0.8, 0.4)).open()
            return
        # Go to new AI Scanner Screen directly!
        self.manager.current = 'scanner'

    def add_patient_reminder(self, instance):
        t = self.pat_time_in.text.strip()
        m = self.pat_med_name.text.strip()
        if ":" in t and m:
            App.get_running_app().reminder_times.append({"time": t, "med": m})
            self.speak(f"Reminder set for {m} at {t}")
            Popup(title="Success", content=Label(text=f"{m} reminder set for {t}"), size_hint=(0.6, 0.3)).open()
            self.pat_time_in.text = ""
            self.pat_med_name.text = ""

    def check_reminders(self, dt):
        now = datetime.now().strftime("%H:%M")
        app = App.get_running_app()
        for reminder in app.reminder_times:
            if reminder['time'] == now and now != app.last_reminded_time:
                app.last_reminded_time = now
                med_name = reminder['med']
                self.status_label.text = f"⏰ TAKE {med_name.upper()} NOW!"
                self.speak(f"It is {now}. Please take your {med_name}.")
                try: notification.notify(title="Medicine Reminder", message=f"Time to take {med_name}!")
                except: pass

    # VOICE LOGIC
    def speak(self, text):
        def _speak():
            if platform == 'android':
                try:
                    from jnius import autoclass
                    Locale = autoclass('java.util.Locale')
                    TextToSpeech = autoclass('android.speech.tts.TextToSpeech')
                    app = App.get_running_app()
                    if not hasattr(app, 'tts_engine'):
                        context = autoclass('org.kivy.android.PythonActivity').mActivity
                        app.tts_engine = TextToSpeech(context, None)
                    app.tts_engine.setLanguage(Locale.US)
                    app.tts_engine.speak(text, TextToSpeech.QUEUE_FLUSH, None, None)
                except Exception as e:
                    print("Android TTS error:", e)
            else:
                try:
                    import pyttsx3, comtypes
                    comtypes.CoInitialize()
                    engine = pyttsx3.init()
                    engine.say(text)
                    engine.runAndWait()
                except Exception as e: print("PC TTS error:", e)
        threading.Thread(target=_speak, daemon=True).start()

    def start_voice_assistant(self, instance):
        self.voice_btn.text = "Listening..."
        threading.Thread(target=self.voice_logic, daemon=True).start()

    def voice_logic(self):
        try:
            r = sr.Recognizer()
            with sr.Microphone() as source:
                r.adjust_for_ambient_noise(source, duration=1)
                audio = r.listen(source, timeout=6, phrase_time_limit=6)
                command = r.recognize_google(audio).lower()
               
                if any(word in command for word in ["help", "call", "emergency"]):
                    self.trigger_emergency()
                    self.speak("Emergency alert sent to your caregiver.")
                elif "time" in command:
                    current_time = datetime.now().strftime("%I:%M %p")
                    self.speak(f"The current time is {current_time}")
                elif "took" in command or "medicine" in command:
                    Clock.schedule_once(lambda dt: self.confirm_med(None))
                    self.speak("Medicine logged.")
                else:
                    self.speak("I heard you say " + command)
        except Exception as e: print("Microphone error:", e)
        Clock.schedule_once(lambda dt: setattr(self.voice_btn, 'text', "TALK TO ASSISTANT 🎙️"))

    def confirm_med(self, instance):
        now = datetime.now().strftime("%I:%M %p")
        App.get_running_app().medicine_log.append(f"Taken: {now}")
        self.status_label.text = "Medicine Logged ✅"

    def trigger_emergency(self, instance=None):
        num = App.get_running_app().emergency_phone
        if platform == 'android':
            try:
                from jnius import autoclass
                PythonActivity = autoclass('org.kivy.android.PythonActivity')
                Intent = autoclass('android.content.Intent')
                Uri = autoclass('android.net.Uri')
                intent = Intent(Intent.ACTION_DIAL)
                intent.setData(Uri.parse(f"tel:{num}"))
                PythonActivity.mActivity.startActivity(intent)
            except Exception as e: print("Dialer error:", e)
        else:
            try: notification.notify(title="ALERT", message=f"Emergency alert sent to {num}")
            except: pass


# --- ALUTH AI SCANNER SCREEN (TFLITE NATIVE) ---
class ScannerScreen(Screen):
    def __init__(self, **kwargs):
        super(ScannerScreen, self).__init__(**kwargs)
        self.layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
       
        self.camera = Camera(resolution=(640, 480), play=False)
        self.layout.add_widget(self.camera)
       
        self.result_label = Label(text="Point Camera and Press SCAN", font_size=20, size_hint_y=0.15, bold=True)
        self.layout.add_widget(self.result_label)
       
        btn_layout = BoxLayout(size_hint_y=0.2, spacing=10)
       
        self.scan_btn = RoundedButton(text="SCAN", font_size=20, bold=True, btn_color=(0, 0.7, 0, 1))
        self.scan_btn.bind(on_press=self.capture_and_predict)
       
        back_btn = RoundedButton(text="GO BACK", font_size=20, bold=True, btn_color=(0.8, 0, 0, 1))
        back_btn.bind(on_press=self.go_back)
       
        btn_layout.add_widget(self.scan_btn)
        btn_layout.add_widget(back_btn)
       
        self.layout.add_widget(btn_layout)
        self.add_widget(self.layout)
       
        self.interpreter = None
        self.labels = []
       
    def load_ai(self):
        if self.interpreter: return
        try:
            self.interpreter = tflite.Interpreter(model_path=MODEL_FILE)
            self.interpreter.allocate_tensors()
            self.input_details = self.interpreter.get_input_details()
            self.output_details = self.interpreter.get_output_details()
            if os.path.exists(LABELS_FILE):
                with open(LABELS_FILE, "r") as f:
                    self.labels = [line.strip() for line in f.readlines()]
            print("TFLite Model Loaded Successfully!")
        except Exception as e:
            print("TFLite Load Error:", e)

    def on_enter(self):
        self.camera.play = True
        self.load_ai()
        if not self.interpreter:
            self.result_label.text = "AI Model Failed to Load!"
           
    def on_leave(self):
        self.camera.play = False

    def capture_and_predict(self, instance):
        if not self.interpreter:
            self.result_label.text = "AI not ready..."
            return
           
        try:
            texture = self.camera.texture
            if not texture: return
            size = texture.size
            pixels = texture.pixels
           
            # Use PIL to resize and convert to NumPy
            pil_image = PILImage.frombytes(mode='RGBA', size=size, data=pixels)
            pil_image = pil_image.convert('RGB')
            pil_image = pil_image.resize((224, 224))
           
            img_array = np.array(pil_image, dtype=np.float32)
            img_array = np.expand_dims(img_array, axis=0)
            img_array = (img_array / 127.5) - 1.0
           
            # TFLite Inference
            self.interpreter.set_tensor(self.input_details[0]['index'], img_array)
            self.interpreter.invoke()
            output_data = self.interpreter.get_tensor(self.output_details[0]['index'])
           
            index = np.argmax(output_data)
            confidence = output_data[0][index]
           
            name = self.labels[index] if (self.labels and len(self.labels) > index) else f"Class {index}"
            self.result_label.text = f"Detected: {name}\nConfidence: {(confidence*100):.1f}%"
           
        except Exception as e:
            print("AI Processing Error:", e)
            self.result_label.text = "Error scanning image"

    def go_back(self, instance):
        self.manager.current = 'patient'

# --- 3. CAREGIVER DASHBOARD ---
class CaregiverScreen(Screen):
    def __init__(self, **kwargs):
        super(CaregiverScreen, self).__init__(**kwargs)
        layout = BoxLayout(orientation='vertical', padding=20, spacing=10)
        layout.add_widget(Label(text="Caregiver Control", font_size=24, bold=True))
       
        self.med_name = TextInput(hint_text="Medicine Name", multiline=False, size_hint_y=None, height=50)
        self.time_input = TextInput(hint_text="Time (e.g., 08:30)", multiline=False, size_hint_y=None, height=50)
       
        add_btn = RoundedButton(text="SET REMINDER", btn_color=(0.1, 0.4, 0.8, 1))
        add_btn.bind(on_press=self.save_reminder)

        self.log_display = Label(text="No activity logs yet", color=(0, 1, 0, 1))
        refresh_btn = RoundedButton(text="REFRESH LOGS", btn_color=(0.1, 0.5, 0.7, 1))
        refresh_btn.bind(on_press=self.update_logs)

        logout_btn = Button(text="Sign Out", size_hint_y=None, height=40, background_color=(0.3, 0.3, 0.3, 1))
        logout_btn.bind(on_press=lambda x: App.get_running_app().logout())

        layout.add_widget(self.med_name)
        layout.add_widget(self.time_input)
        layout.add_widget(add_btn)
        layout.add_widget(self.log_display)
        layout.add_widget(refresh_btn)
        layout.add_widget(logout_btn)
        self.add_widget(layout)

    def save_reminder(self, instance):
        t = self.time_input.text.strip()
        m = self.med_name.text.strip()
        if ":" in t and m:
            App.get_running_app().reminder_times.append({"time": t, "med": m})
            self.time_input.text = ""
            self.med_name.text = ""
            Popup(title="Success", content=Label(text=f"Reminder set for {m} at {t}"), size_hint=(0.5, 0.3)).open()

    def update_logs(self, instance):
        logs = App.get_running_app().medicine_log
        self.log_display.text = "\n".join(logs[-5:]) if logs else "No activity yet."


# --- 4. MAIN APP ---
class CareApp(App):
    def build(self):
        if platform == 'android':
            from android.permissions import request_permissions, Permission
            try:
                request_permissions([
                    Permission.CAMERA,
                    Permission.RECORD_AUDIO,
                    Permission.WRITE_EXTERNAL_STORAGE,
                    Permission.READ_EXTERNAL_STORAGE,
                    Permission.INTERNET
                ])
            except Exception as e: print("Permission request error:", e)

        self.reset_state()
        self.sm = ScreenManager()
        self.sm.add_widget(LoginScreen(name='login'))
        self.sm.add_widget(PatientScreen(name='patient'))
        self.sm.add_widget(ScannerScreen(name='scanner'))
        self.sm.add_widget(CaregiverScreen(name='caregiver'))
       
        if os.path.exists(CONFIG_FILE):
            Clock.schedule_once(self.check_auto_login, 0.1)
        return self.sm

    def reset_state(self):
        self.emergency_phone = ""
        self.medicine_log = []
        self.reminder_times = []
        self.last_reminded_time = ""

    def check_auto_login(self, dt):
        try:
            with open(CONFIG_FILE, "r") as f:
                data = json.load(f)
                self.emergency_phone = data['phone']
                self.sm.current = 'caregiver' if data['username'] == "caregiver" else 'patient'
        except: pass

    def logout(self):
        if os.path.exists(CONFIG_FILE): os.remove(CONFIG_FILE)
        self.reset_state()
        self.sm.current = 'login'

if __name__ == '__main__':
    CareApp().run()

