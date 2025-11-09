import json
import os
import logging
from datetime import datetime
import uuid

try:
    from kivy.app import App
    from kivy.uix.boxlayout import BoxLayout
    from kivy.uix.textinput import TextInput
    from kivy.uix.button import Button
    from kivy.clock import Clock
    from kivy.uix.label import Label
except Exception:
    raise SystemExit("Kivy 모듈을 불러올 수 없습니다. Android에서 실행하거나 Kivy를 설치하세요.")

# plyer optional
try:
    from plyer import notification
    def notify(title, message):
        try:
            notification.notify(title=title, message=message, timeout=5)
        except Exception:
            logging.exception("plyer 알림 실패")
else:
    def notify(title, message):
        logging.info("NOTIFY: %s - %s", title, message)

DATA_FILE = os.path.join(os.path.dirname(__file__), "alarms.json")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

def ensure_data_file():
    if not os.path.exists(DATA_FILE):
        save_alarms([])

def load_alarms():
    ensure_data_file()
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        logging.exception("alarms.json 로드 실패 - 빈 리스트로 초기화")
        return []

def save_alarms(alarms):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(alarms, f, ensure_ascii=False, indent=2)
    except Exception:
        logging.exception("alarms.json 저장 실패")

def normalize_time_token(tok):
    tok = tok.strip()
    parts = tok.split(":")
    if len(parts) == 2:
        return f"{int(parts[0]):02d}:{int(parts[1]):02d}:00"
    if len(parts) == 3:
        return f"{int(parts[0]):02d}:{int(parts[1]):02d}:{int(parts[2]):02d}"
    return tok

class MainLayout(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", **kwargs)
        self.alarms = load_alarms()
        self.add_widget(Label(text="앱용 Calendar Alarm Clock"))
        self.name = TextInput(hint_text="이름", size_hint_y=None, height=40)
        self.add_widget(self.name)
        self.time = TextInput(hint_text="시간 HH:MM 또는 HH:MM:SS (콤마구분)", size_hint_y=None, height=40)
        self.add_widget(self.time)
        self.rec = TextInput(hint_text="반복( daily / weekly / monthly / yearly / interval )", size_hint_y=None, height=40)
        self.add_widget(self.rec)
        btn = Button(text="추가", size_hint_y=None, height=50)
        btn.bind(on_release=self.add_alarm)
        self.add_widget(btn)
        self.status = Label(text="")
        self.add_widget(self.status)
        Clock.schedule_interval(self.check_alarms, 1)

    def add_alarm(self, *args):
        times = [normalize_time_token(t) for t in self.time.text.split(",") if t.strip()]
        a = {"id": str(uuid.uuid4()), "name": self.name.text or "알람", "recurrence": self.rec.text or "daily",
             "times": times, "enabled": True, "last_triggered": ""}
        self.alarms.append(a)
        save_alarms(self.alarms)
        self.status.text = "저장됨"
        self.name.text = ""
        self.time.text = ""
        self.rec.text = ""

    def check_alarms(self, dt):
        now = datetime.now()
        cur_t = now.strftime("%H:%M:%S")
        changed = False
        for a in self.alarms:
            if not a.get("enabled", True):
                continue
            for t in a.get("times", []):
                if cur_t.startswith(t):
                    if a.get("last_triggered") == now.strftime("%Y-%m-%d %H:%M:%S"):
                        continue
                    a["last_triggered"] = now.strftime("%Y-%m-%d %H:%M:%S")
                    notify(title="Alarm", message=f"{a.get('name')}\n{a.get('recurrence')}")
                    changed = True
        if changed:
            save_alarms(self.alarms)

class AlarmApp(App):
    def build(self):
        ensure_data_file()
        return MainLayout()

if __name__ == "__main__":
    AlarmApp().run()