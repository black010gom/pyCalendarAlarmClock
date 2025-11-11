import os
import sys
import tkinter as tk
from tkinter import filedialog
import winsound

def select_music_file():
    # 기본 음악 폴더 경로
    default_music_folder = os.path.join(os.path.expanduser("~"), "Music")
    # 파일 선택 대화상자 열기
    music_file = filedialog.askopenfilename(initialdir=default_music_folder, title="음악 파일 선택",
                                             filetypes=(("음악 파일", "*.mp3;*.wav"), ("모든 파일", "*.*")))
    return music_file

def play_music(file_path):
    if os.path.exists(file_path):
        winsound.PlaySound(file_path, winsound.SND_FILENAME)