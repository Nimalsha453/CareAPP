import os
import json
import threading
from datetime import datetime

# Buildozer requirements
try:
    import requests
except Exception as e: 
    print("Requests parsing error:", e)

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
    from PIL import Image as PILImage
except: pass

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

CONFIG_FILE = "user_session.json"
TEMP_IMAGE_PATH = "temp_scan.jpg"

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

class LoginScreen(Screen):
    def __init__(self, **kwargs):
        super(LoginScreen, self).__init__(**kwargs)
        layout = BoxLayout(orientation='vertical', padding=40, spacing=15)
        layout.add_widget(Label(text="CARE APP", font_size=42, bold=True))
       
        self.username = TextInput(hint_text="Username (patient/caregiver)", multiline=False, size_hint_y=None, height=50)
        self.phone_input = TextInput(hint_text="Caregiver Mobile No", multiline=False, size_hint_y=None, height=50)
       
        login_btn = RoundedButton(text="LOG IN", font_size=20, bold=True, size_hint_y=None, height=60)
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

class PatientScreen(Screen):
    def __init__(self, **kwargs):
        super(PatientScreen, self).__init__(**kwargs)
        layout = BoxLayout(orientation='vertical', padding=25, spacing=15)
       
        self.status_label = Label(text="Patient Dashboard", font_size=24, bold=True, size_hint_y=0.1)
        layout.add_widget(self.status_label)
       
        remind_box = BoxLayout(orientation='horizontal', spacing=10, size_hint_y=0.15)
        self.pat_med_name = TextInput(hint_text="Med Name", multiline=False)
        self.pat_time_in = TextInput(hint_text="HH:MM", multiline=False)
        add_rem_btn = RoundedButton(text="SET REMINDER") 
        add_rem_btn.bind(on_press=self.add_patient_reminder)
        remind_box.add_widget(self.pat_med_name)
        remind_box.add_widget(self.pat_time_in)
        remind_box.add_widget(add_rem_btn)
        layout.add_widget(remind_box)

        self.voice_btn = RoundedButton(text="TALK TO ASSISTANT🎙️", size_hint_y=0.15)
        self.voice_btn.bind(on_press=self.start_voice_assistant)
        layout.add_widget(self.voice_btn)

        med_btn = RoundedButton(text="I TOOK MY MEDICINE✅", size_hint_y=0.15)
        med_btn.bind(on_press=self.confirm_med)
        layout.add_widget(med_btn)

        scan_btn = RoundedButton(text="SCAN MEDICINE (AI)📷", size_hint_y=0.15)
        scan_btn.bind(on_press=self.start_scanner)
        layout.add_widget(scan_btn)

        emer_btn = RoundedButton(text="HELP / EMERGENCY 🚨", size_hint_y=0.2, font_size=24, bold=True, btn_color=(0.8, 0, 0, 1))
        emer_btn.bind(on_press=self.trigger_emergency)
        layout.add_widget(emer_btn)

        logout_btn = Button(text="Sign Out", size_hint_y=None, height=40, background_color=(0.3, 0.3, 0.3, 1))
        logout_btn.bind(on_press=lambda x: App.get_running_app().logout())
        layout.add_widget(logout_btn)

        self.add_widget(layout)
        Clock.schedule_interval(self.check_reminders, 30)

    def start_scanner(self, instance):
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

# --- CLIENT-SERVER SCANNER (NEW!) ---
class ScannerScreen(Screen):
    def __init__(self, **kwargs):
        super(ScannerScreen, self).__init__(**kwargs)
        self.layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        
        # User types their laptop IP here
        self.ip_input = TextInput(hint_text="Enter Laptop WiFi IP (e.g. 192.168.1.5)", size_hint_y=0.1, font_size=20, multiline=False)
        self.layout.add_widget(self.ip_input)
        
        self.camera = Camera(resolution=(640, 480), play=False)
        self.layout.add_widget(self.camera)
        
        self.result_label = Label(text="Point Camera at Medicine & PRESS SCAN", font_size=20, size_hint_y=0.15, bold=True)
        self.layout.add_widget(self.result_label)
        
        btn_layout = BoxLayout(size_hint_y=0.2, spacing=10)
        
        scan_btn = RoundedButton(text="SCAN", font_size=24, bold=True, btn_color=(0, 0.7, 0, 1))
        scan_btn.bind(on_press=self.capture_and_predict)
        
        back_btn = RoundedButton(text="GO BACK", font_size=22, bold=True, btn_color=(0.8, 0, 0, 1))
        back_btn.bind(on_press=self.go_back)
        
        btn_layout.add_widget(scan_btn)
        btn_layout.add_widget(back_btn)
        
        self.layout.add_widget(btn_layout)
        self.add_widget(self.layout)

    def on_enter(self):
        self.camera.play = True
            
    def on_leave(self):
        self.camera.play = False

    def capture_and_predict(self, instance):
        ip = self.ip_input.text.strip()
        if not ip:
            self.result_label.text = "Please enter Laptop IP!"
            return
            
        self.result_label.text = "Capturing Image..."
        try:
            texture = self.camera.texture
            if not texture:
                self.result_label.text = "Camera not ready!"
                return
            
            size = texture.size
            pixels = texture.pixels
            
            # Use PIL to convert camera frame to JPEG
            pil_image = PILImage.frombytes(mode='RGBA', size=size, data=pixels)
            pil_image = pil_image.convert('RGB')
            pil_image.save(TEMP_IMAGE_PATH, format='JPEG', quality=85)
            
            self.result_label.text = "Sending to Laptop for AI Analysis..."
            threading.Thread(target=self.send_to_server, args=(ip,), daemon=True).start()
            
        except Exception as e:
            print("Capture Error:", e)
            self.result_label.text = "Camera Error!"

    def send_to_server(self, ip):
        url = f"http://{ip}:5000/predict"
        msg = ""
        try:
            with open(TEMP_IMAGE_PATH, 'rb') as f:
                # HTTP POST logic
                files = {'image': ('scan.jpg', f, 'image/jpeg')}
                response = requests.post(url, files=files, timeout=8) # 8 seconds max wait
            
            if response.status_code == 200:
                data = response.json()
                pill = data.get('prediction', 'Unknown')
                conf = data.get('confidence', 0.0)
                msg = f"AI Says: {pill}\nConfidence: {conf}%"
            else:
                msg = f"Laptop Error ({response.status_code})"
                
        except requests.exceptions.Timeout:
            msg = "Timeout! Check IP address or Laptop Firewall."
        except requests.exceptions.ConnectionError:
            msg = "Connection Failed! Is server.py running on Laptop?"
        except Exception as e:
            msg = f"Network Error: {type(e).__name__}"
            
        Clock.schedule_once(lambda dt: self.update_result(msg))

    def update_result(self, msg):
        self.result_label.text = msg

# --- 3. CAREGIVER DASHBOARD ---
class CaregiverScreen(Screen):
    def __init__(self, **kwargs):
        super(CaregiverScreen, self).__init__(**kwargs)
        layout = BoxLayout(orientation='vertical', padding=20, spacing=10)
        layout.add_widget(Label(text="Caregiver Dashboard", font_size=24, bold=True))
       
        self.med_name = TextInput(hint_text="Medicine Name", multiline=False, size_hint_y=None, height=50)
        self.time_input = TextInput(hint_text="Time (e.g., 08:30)", multiline=False, size_hint_y=None, height=50)
       
        add_btn = RoundedButton(text="SET REMINDER")
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
            except: pass

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

