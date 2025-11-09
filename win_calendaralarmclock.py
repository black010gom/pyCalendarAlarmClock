import os
import sys
import json
import threading
import time
import uuid
import logging
import calendar
from datetime import datetime
# tkinter 안전 로드
try:
    import tkinter as tk
    from tkinter import simpledialog, messagebox, ttk
except Exception as e:
    raise SystemExit("tkinter을 사용할 수 없습니다. Python 설치 시 'tcl/tk' 포함했는지 확인하세요.") from e

# 사운드 처리 (winsound 또는 대체)
try:
    import winsound

    def beep_alert():
        for _ in range(3):
            winsound.Beep(1000, 300)
            time.sleep(0.1)
except Exception:
    import ctypes
    MB_ICONASTERISK = 0x40

    def beep_alert():
        for _ in range(3):
            try:
                ctypes.windll.user32.MessageBeep(MB_ICONASTERISK)
            except Exception:
                pass
            time.sleep(0.2)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# 데이터 파일 위치 (PyInstaller onefile 대비)
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.join(os.getenv("LOCALAPPDATA") or os.path.expanduser("~"), "win_calendaralarmclock")
    os.makedirs(BASE_DIR, exist_ok=True)
else:
    BASE_DIR = os.path.dirname(__file__)
DATA_FILE = os.path.join(BASE_DIR, "alarms.json")
calendar.setfirstweekday(calendar.MONDAY)

# 반복 문자열 매핑 (화면용 한국어 <-> 내부 영문)
REC_MAP = {"매일": "daily", "매주": "weekly", "매월": "monthly", "매년": "yearly", "간격": "interval"}
REC_MAP_INV = {v: k for k, v in REC_MAP.items()}

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

def parse_time_token(tok):
    tok = tok.strip()
    if not tok:
        return None
    parts = tok.split(":")
    try:
        if len(parts) == 2:
            return f"{int(parts[0]):02d}:{int(parts[1]):02d}:00"
        if len(parts) == 3:
            return f"{int(parts[0]):02d}:{int(parts[1]):02d}:{int(parts[2]):02d}"
    except Exception:
        return None
    return None

def time_matches_spec(now, spec):
    cur = now.strftime("%H:%M:%S")
    return cur.startswith(spec)

def should_trigger(alarm, now):
    if not alarm.get("enabled", True):
        return False
    # 기간 검사(선택)
    ps = alarm.get("period_start") or alarm.get("start_date")
    pe = alarm.get("period_end")
    if ps:
        try:
            start_dt = datetime.fromisoformat(ps)
            if now < start_dt:
                return False
        except Exception:
            return False
    if pe:
        try:
            end_dt = datetime.fromisoformat(pe)
            if now > end_dt:
                return False
        except Exception:
            return False

    times = alarm.get("times", [])
    if not times:
        return False
    if not any(time_matches_spec(now, t) for t in times):
        return False

    last = alarm.get("last_triggered")
    if last == now.strftime("%Y-%m-%d %H:%M:%S"):
        return False

    rt = alarm.get("recurrence", "daily")
    if rt == "daily":
        return True
    if rt == "weekly":
        weekdays = alarm.get("weekdays", [])
        return now.weekday() in weekdays
    if rt == "monthly":
        day = alarm.get("day_of_month")
        return day == now.day
    if rt == "yearly":
        m = alarm.get("month")
        d = alarm.get("day")
        return (m == now.month and d == now.day)
    if rt == "interval":
        # 핵심: interval_offsets(1-based)로 간격내 어떤 날에 울릴지 결정
        interval = max(1, int(alarm.get("interval_days", 1)))
        start = alarm.get("period_start") or alarm.get("start_date")
        if not start:
            # 시작일이 없으면 매 interval마다(즉 delta 기준 없음) 동작으로 간주
            return True
        try:
            start_date = datetime.fromisoformat(start).date()
            delta = (now.date() - start_date).days
            if delta < 0:
                return False
            pos = (delta % interval) + 1  # 1 기반 위치
            offsets = alarm.get("interval_offsets")  # 예: [1,3]
            if offsets:
                return int(pos) in [int(x) for x in offsets]
            else:
                # offsets 지정 없으면 기본적으로 매 interval의 첫날(pos==1)만 동작
                return pos == 1
        except Exception:
            return False
    return False

# 간단 툴팁 클래스 (tkinter에 툴팁 추가)
class Tooltip:
    def __init__(self, widget, text, delay=400):
        self.widget = widget
        self.text = text
        self.delay = delay
        self._id = None
        self.tw = None
        widget.bind("<Enter>", self._enter, add="+")
        widget.bind("<Leave>", self._leave, add="+")
        widget.bind("<ButtonPress>", self._leave, add="+")

    def _enter(self, _):
        self._id = self.widget.after(self.delay, self.show)

    def _leave(self, _):
        if self._id:
            self.widget.after_cancel(self._id)
            self._id = None
        self.hide()

    def show(self):
        if self.tw:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 1
        self.tw = tk.Toplevel(self.widget)
        self.tw.wm_overrideredirect(True)
        self.tw.wm_geometry(f"+{x}+{y}")
        lbl = ttk.Label(self.tw, text=self.text, background="#ffffe0", relief="solid", borderwidth=1)
        lbl.pack(ipadx=4, ipady=2)

    def hide(self):
        if self.tw:
            try:
                self.tw.destroy()
            except Exception:
                pass
            self.tw = None

class AddAlarmDialog(simpledialog.Dialog):
    def __init__(self, parent, prefill_date=None):
        self.prefill_date = prefill_date
        super().__init__(parent, title="알람 추가")

    def body(self, master):
        # 변경: "이름:" -> "제목:"
        ttk.Label(master, text="제목:").grid(row=0, column=0, sticky="w")
        self.name = ttk.Entry(master)
        self.name.grid(row=0, column=1, sticky="ew")

        ttk.Label(master, text="반복:").grid(row=1, column=0, sticky="w")
        self.rec = tk.StringVar(value="매일")
        self.rec_combo = ttk.Combobox(master, textvariable=self.rec, values=list(REC_MAP.keys()), state="readonly")
        self.rec_combo.grid(row=1, column=1, sticky="ew")
        Tooltip(self.rec_combo, "반복 주기 선택: 매일/매주/매월/매년/간격")

        ttk.Label(master, text="시간(콤마구분 HH:MM 또는 HH:MM:SS):").grid(row=2, column=0, sticky="w")
        self.times = ttk.Entry(master)
        self.times.grid(row=2, column=1, sticky="ew")
        Tooltip(self.times, "예: 09:00,13:30 또는 07:00:00 — 여러 시간은 콤마로 구분")

        ttk.Label(master, text="주(0=월-6=일,콤마):").grid(row=3, column=0, sticky="w")
        self.weekdays = ttk.Entry(master)
        self.weekdays.grid(row=3, column=1, sticky="ew")
        Tooltip(self.weekdays, "매주 선택 시 요일 번호 입력(예: 0,2 = 월,수)")

        ttk.Label(master, text="월의 날짜(DD):").grid(row=4, column=0, sticky="w")
        self.day_of_month = ttk.Entry(master)
        self.day_of_month.grid(row=4, column=1, sticky="ew")
        Tooltip(self.day_of_month, "매월 특정 일에 알람 설정(예: 15)")

        ttk.Label(master, text="간격일수(예: 3 = 3일마다):").grid(row=5, column=0, sticky="w")
        self.interval = ttk.Entry(master)
        self.interval.grid(row=5, column=1, sticky="ew")
        Tooltip(self.interval, "간격 반복일수 입력: 시작일부터 매 N일마다 실행")

        ttk.Label(master, text="간격내 활성일(예: 1,3 — 1은 시작일, 추가는 & 로 연결):").grid(row=6, column=0, sticky="w")
        self.interval_offsets = ttk.Entry(master)
        self.interval_offsets.grid(row=6, column=1, sticky="ew")
        Tooltip(self.interval_offsets, "예: 1,3 또는 1,3&5  — '&'로 추가 그룹 연결, 숫자만 사용, 최대 5개 (중복 자동 제거)")

        ttk.Label(master, text="기간 시작(YYYY-MM-DD HH:MM:SS, 선택):").grid(row=7, column=0, sticky="w")
        self.period_start = ttk.Entry(master)
        self.period_start.grid(row=7, column=1, sticky="ew")
        Tooltip(self.period_start, "알람이 유효한 기간의 시작 시각 입력(예: 2025-11-08 09:00:00)")

        ttk.Label(master, text="기간 종료(YYYY-MM-DD HH:MM:SS, 선택):").grid(row=8, column=0, sticky="w")
        self.period_end = ttk.Entry(master)
        self.period_end.grid(row=8, column=1, sticky="ew")
        Tooltip(self.period_end, "알람이 유효한 기간의 종료 시각 입력(예: 2025-11-15 18:00:00)")

        # prefill 날짜 보조
        if self.prefill_date:
            y, m, d = self.prefill_date
            self.period_start.insert(0, f"{y:04d}-{m:02d}-{d:02d} 09:00:00")
            self.period_end.insert(0, f"{y:04d}-{m:02d}-{d:02d} 21:00:00")

        return self.name

    def validate(self):
        # interval_offsets 검증 및 파싱 ('&'와 ',' 허용), 최대 5개
        s = self.interval_offsets.get().strip()
        if not s:
            self._parsed_offsets = []
            return True
        parts = s.split("&")
        vals = []
        for part in parts:
            for tok in part.split(","):
                t = tok.strip()
                if not t:
                    continue
                if not t.isdigit():
                    messagebox.showerror("오류", "간격내 활성일은 숫자(정수)와 콤마/& 만 허용합니다.")
                    return False
                v = int(t)
                if v <= 0:
                    messagebox.showerror("오류", "간격내 활성일은 1 이상의 값이어야 합니다.")
                    return False
                vals.append(v)
        # 중복 제거(입력 순서 유지)
        unique = []
        for v in vals:
            if v not in unique:
                unique.append(v)
        if len(unique) > 5:
            messagebox.showerror("오류", "간격내 활성일은 최대 5개까지만 설정할 수 있습니다.")
            return False
        self._parsed_offsets = unique
        return True

    def buttonbox(self):
        box = ttk.Frame(self)
        ok = ttk.Button(box, text="확인", width=10, command=self.ok, default="active")
        ok.pack(side="left", padx=5, pady=5)
        cancel = ttk.Button(box, text="취소", width=10, command=self.cancel)
        cancel.pack(side="left", padx=5, pady=5)
        self.bind("<Return>", self.ok)
        self.bind("<Escape>", self.cancel)
        box.pack()

    def _generate_times_for_count(self, count, start_hour=9, end_hour=21):
        try:
            cnt = int(count)
            if cnt <= 0:
                return []
        except Exception:
            return []
        if cnt == 1:
            return [f"{start_hour:02d}:00:00"]
        total_minutes = (end_hour - start_hour) * 60
        step = total_minutes / (cnt - 1)
        times = []
        for i in range(cnt):
            mins = round(start_hour * 60 + step * i)
            h = (mins // 60) % 24
            m = mins % 60
            times.append(f"{int(h):02d}:{int(m):02d}:00")
        return times

    def apply(self):
        rec_kor = self.rec.get()
        rec_en = REC_MAP.get(rec_kor, "daily")
        raw_times = [t.strip() for t in self.times.get().split(",") if t.strip()]
        alarm = {"name": self.name.get() or "알람", "recurrence": rec_en, "times": raw_times, "enabled": True}

        if self.weekdays.get().strip():
            try:
                alarm["weekdays"] = [int(x) for x in self.weekdays.get().split(",") if x.strip()]
            except Exception:
                alarm["weekdays"] = []

        if self.day_of_month.get().strip():
            try:
                alarm["day_of_month"] = int(self.day_of_month.get())
            except Exception:
                pass

        if self.interval.get().strip():
            try:
                alarm["interval_days"] = int(self.interval.get())
            except Exception:
                alarm["interval_days"] = 1

        # 검증된 parsed offsets 저장
        alarm["interval_offsets"] = getattr(self, "_parsed_offsets", [])

        if self.period_start.get().strip():
            alarm["period_start"] = self.period_start.get().strip()
        if self.period_end.get().strip():
            alarm["period_end"] = self.period_end.get().strip()

        # 간격(recurrence == 'interval')이고 times 비어있고 interval_count가 있으면 자동 시간 생성(기존 로직 유지)
        if alarm.get("recurrence") == "interval" and (not alarm.get("times")):
            cnt = alarm.get("interval_count") or 0
            if cnt > 0:
                alarm["times"] = self._generate_times_for_count(cnt)

        self.result = alarm

class AlarmApp:
    def __init__(self, root):
        self.root = root
        root.title("캘린더 알람 시계")
        self.alarms = load_alarms()
        self.current_year = datetime.now().year
        self.current_month = datetime.now().month
        self.build_ui()
        self.running = True
        t = threading.Thread(target=self.scheduler_loop, daemon=True)
        t.start()

    def build_ui(self):
        # 상단: 달력 네비게이션
        top_frame = ttk.Frame(self.root, padding=6)
        top_frame.pack(fill="x")
        self.prev_btn = ttk.Button(top_frame, text="◀ 이전달", command=self.go_prev_month)
        self.prev_btn.pack(side="left")
        Tooltip(self.prev_btn, "이전 달 보기")
        self.month_label = ttk.Label(top_frame, text="", anchor="center", width=20)
        self.month_label.pack(side="left", expand=True)
        self.next_btn = ttk.Button(top_frame, text="다음달 ▶", command=self.go_next_month)
        self.next_btn.pack(side="right")
        Tooltip(self.next_btn, "다음 달 보기")

        # 달력 그리드
        cal_frame = ttk.Frame(self.root, padding=6, relief="flat")
        cal_frame.pack(fill="both")
        self.cal_frame = cal_frame
        # weekday header (한국어)
        weekday_names = ["월", "화", "수", "목", "금", "토", "일"]
        header = ttk.Frame(cal_frame)
        header.pack(fill="x")
        for i, wd in enumerate(weekday_names):
            lbl = ttk.Label(header, text=wd, width=6, anchor="center")
            lbl.grid(row=0, column=i, padx=2, pady=2)

        self.days_grid = ttk.Frame(cal_frame)
        self.days_grid.pack()

        # 하단: 알람 리스트와 조작 버튼 (한글)
        bottom = ttk.Frame(self.root, padding=6)
        bottom.pack(fill="both", expand=True)
        self.listbox = tk.Listbox(bottom, height=8)
        self.listbox.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(bottom, orient="vertical", command=self.listbox.yview)
        scrollbar.pack(side="left", fill="y")
        self.listbox.config(yscrollcommand=scrollbar.set)

        btn_frame = ttk.Frame(self.root, padding=6)
        btn_frame.pack(fill="x")
        self.btn_add = ttk.Button(btn_frame, text="알람 추가", command=self.add_alarm)
        self.btn_add.pack(side="left")
        Tooltip(self.btn_add, "새로운 알람을 추가합니다")
        self.btn_del = ttk.Button(btn_frame, text="삭제", command=self.delete_alarm)
        self.btn_del.pack(side="left")
        Tooltip(self.btn_del, "선택한 알람을 삭제합니다")
        self.btn_toggle = ttk.Button(btn_frame, text="사용/비사용 토글", command=self.toggle_alarm)
        self.btn_toggle.pack(side="left")
        Tooltip(self.btn_toggle, "선택한 알람을 사용 또는 비사용으로 전환합니다")
        self.btn_refresh = ttk.Button(btn_frame, text="새로고침", command=self.refresh_list)
        self.btn_refresh.pack(side="left")
        Tooltip(self.btn_refresh, "알람 목록을 새로 불러옵니다")

        self.refresh_list()
        self.draw_calendar()

    def refresh_list(self):
        self.alarms = load_alarms()
        self.listbox.delete(0, tk.END)
        for a in self.alarms:
            times = ",".join(a.get("times", []))
            en = "사용" if a.get("enabled", True) else "비사용"
            rec_kor = REC_MAP_INV.get(a.get("recurrence"), a.get("recurrence"))
            line = f"{a.get('name','(이름없음)')} | {rec_kor} | {times} | {en}"
            self.listbox.insert(tk.END, line)

    def add_alarm(self, prefill_date=None):
        dlg = AddAlarmDialog(self.root, prefill_date=prefill_date)
        alarm = dlg.result
        if alarm:
            alarm["times"] = [parse_time_token(t) or t for t in alarm.get("times", [])]
            alarm["id"] = str(uuid.uuid4())
            alarm["last_triggered"] = ""
            self.alarms.append(alarm)
            save_alarms(self.alarms)
            self.refresh_list()

    def delete_alarm(self):
        sel = self.listbox.curselection()
        if not sel:
            messagebox.showinfo("안내", "삭제할 알람을 선택하세요.")
            return
        idx = sel[0]
        if messagebox.askyesno("확인", "선택한 알람을 삭제하시겠습니까?"):
            self.alarms.pop(idx)
            save_alarms(self.alarms)
            self.refresh_list()

    def toggle_alarm(self):
        sel = self.listbox.curselection()
        if not sel:
            messagebox.showinfo("안내", "토글할 알람을 선택하세요.")
            return
        idx = sel[0]
        self.alarms[idx]["enabled"] = not self.alarms[idx].get("enabled", True)
        save_alarms(self.alarms)
        self.refresh_list()

    def go_prev_month(self):
        if self.current_month == 1:
            self.current_year -= 1
            self.current_month = 12
        else:
            self.current_month -= 1
        self.draw_calendar()

    def go_next_month(self):
        if self.current_month == 12:
            self.current_year += 1
            self.current_month = 1
        else:
            self.current_month += 1
        self.draw_calendar()

    def draw_calendar(self):
        # 제목
        self.month_label.config(text=f"{self.current_year}년 {self.current_month}월")
        # clear grid
        for child in self.days_grid.winfo_children():
            child.destroy()
        month_days = calendar.monthcalendar(self.current_year, self.current_month)
        for r, week in enumerate(month_days):
            for c, day in enumerate(week):
                if day == 0:
                    lbl = ttk.Label(self.days_grid, text="", width=6)
                    lbl.grid(row=r, column=c, padx=2, pady=2)
                else:
                    btn = ttk.Button(self.days_grid, text=str(day), width=6)
                    btn.grid(row=r, column=c, padx=2, pady=2)
                    def make_cmd(d):
                        return lambda ev=None: self.add_alarm(prefill_date=(self.current_year, self.current_month, d))
                    btn.config(command=make_cmd(day))
                    # 오늘 강조
                    if (self.current_year, self.current_month, day) == (datetime.now().year, datetime.now().month, datetime.now().day):
                        btn.state(["!disabled"])
                        btn.config(style="Today.TButton")
        # 스타일: 오늘 강조(간단)
        style = ttk.Style()
        style.configure("Today.TButton", foreground="blue")

    def scheduler_loop(self):
        while self.running:
            now = datetime.now()
            changed = False
            for alarm in list(self.alarms):
                try:
                    if should_trigger(alarm, now):
                        alarm["last_triggered"] = now.strftime("%Y-%m-%d %H:%M:%S")
                        save_alarms(self.alarms)
                        changed = True
                        threading.Thread(target=self.fire_alarm, args=(alarm,), daemon=True).start()
                except Exception:
                    logging.exception("스케줄러 오류")
            if changed:
                self.root.after(0, self.refresh_list)
            time.sleep(1)

    def fire_alarm(self, alarm):
        rec_kor = REC_MAP_INV.get(alarm.get("recurrence"), alarm.get("recurrence"))
        msg = f"알람: {alarm.get('name')}\n{rec_kor} at {','.join(alarm.get('times', []))}"
        try:
            self.root.after(0, lambda: messagebox.showinfo("알람", msg))
        except Exception:
            logging.exception("팝업 실패")
        try:
            beep_alert()
        except Exception:
            logging.exception("비프 실패")

if __name__ == "__main__":
    ensure_data_file()
    root = tk.Tk()
    app = AlarmApp(root)
    def on_close():
        app.running = False
        save_alarms(app.alarms)
        root.destroy()
    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()