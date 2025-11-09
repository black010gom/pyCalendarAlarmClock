# Calendar Alarm Clock (캘린더 알람 시계)

## 프로젝트 개요
Python으로 제작된 캘린더 기반 알람 시계 애플리케이션

## 기능
- 일정 관리와 알람 기능 통합
- 다양한 반복 설정 (매일, 매주, 매월, 매년, 간격)
- 실시간 알람 및 로그 기록

## 파일 구조
- `win_calendaralarmclock.py`: 메인 애플리케이션
- `logCalendarAlarmClock.py`: 로그 처리 모듈

## 무시되는 파일 (.gitignore)
1. Python 관련
   - 바이트 코드 (`__pycache__/`, `*.pyc`)
   - 빌드 파일 (`build/`, `dist/`)
   - PyInstaller 파일 (`*.spec`)

2. 환경 설정
   - 가상환경 폴더 (`venv/`, `.env`)
   - IDE 설정 (`.vscode/`, `.idea/`)

3. 로그/임시 파일
   - 로그 파일 (`*.log`)
   - 알람 로그 폴더 (`CalendarAlarmClock*/`)

## 버전 관리
- 2025-11-08: 초기 버전 테스트 진행 중
