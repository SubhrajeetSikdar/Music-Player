import pygame
import tkinter as tk
from tkinter import filedialog
import os
import random
from mutagen.mp3 import MP3

# -------------------- WINDOW --------------------
root = tk.Tk()
root.title("🔥 Advanced Music Player")
root.geometry("520x520")
root.config(bg="#121212")

# -------------------- PYGAME --------------------
pygame.init()
pygame.mixer.init()

songs = []
current_index = 0
is_paused = False
shuffle_mode = False

# -------------------- FUNCTIONS --------------------

def add_songs():
    global songs
    new_songs = filedialog.askopenfilenames(
        title="Select Songs",
        filetypes=[("MP3 Files", "*.mp3")]
    )
    for song in new_songs:
        songs.append(song)
        playlist.insert(tk.END, os.path.basename(song))


def play_song():
    global current_index, is_paused
    try:
        current_index = playlist.curselection()[0]
    except:
        current_index = 0

    song = songs[current_index]
    pygame.mixer.music.load(song)
    pygame.mixer.music.play()
    song_var.set("Playing: " + os.path.basename(song))
    is_paused = False
    show_progress()
    auto_next()


def stop_song():
    pygame.mixer.music.stop()
    song_var.set("Stopped")


def pause_song():
    global is_paused
    pygame.mixer.music.pause()
    is_paused = True
    song_var.set("Paused")


def resume_song():
    global is_paused
    pygame.mixer.music.unpause()
    is_paused = False
    song_var.set("Resumed")


def next_song():
    global current_index
    if shuffle_mode:
        current_index = random.randint(0, len(songs)-1)
    else:
        current_index = (current_index + 1) % len(songs)

    playlist.selection_clear(0, tk.END)
    playlist.selection_set(current_index)
    playlist.activate(current_index)
    play_song()


def prev_song():
    global current_index
    current_index = (current_index - 1) % len(songs)
    playlist.selection_clear(0, tk.END)
    playlist.selection_set(current_index)
    playlist.activate(current_index)
    play_song()


def set_volume(val):
    volume = int(val)/100
    pygame.mixer.music.set_volume(volume)


def toggle_shuffle():
    global shuffle_mode
    shuffle_mode = not shuffle_mode
    if shuffle_mode:
        shuffle_btn.config(bg="green")
    else:
        shuffle_btn.config(bg="gray")


# -------------------- PROGRESS --------------------
def show_progress():
    if pygame.mixer.music.get_busy():
        try:
            song = songs[current_index]
            audio = MP3(song)
            total_length = int(audio.info.length)
            current_time = pygame.mixer.music.get_pos() // 1000

            progress.config(text=f"{current_time} / {total_length} sec")
        except:
            pass

        root.after(1000, show_progress)


# -------------------- AUTO NEXT --------------------
def auto_next():
    if pygame.mixer.music.get_busy():
        root.after(2000, auto_next)
    else:
        next_song()


# -------------------- UI --------------------
title = tk.Label(root, text="🎧 ADVANCED MUSIC PLAYER", 
                 font=("Arial", 18, "bold"),
                 bg="#121212", fg="white")
title.pack(pady=10)

song_var = tk.StringVar()
song_var.set("No song playing")

song_label = tk.Label(root, textvariable=song_var,
                      font=("Arial", 12),
                      bg="#121212", fg="cyan")
song_label.pack()

progress = tk.Label(root, text="0/0", bg="#121212", fg="white")
progress.pack(pady=5)

# Playlist
playlist = tk.Listbox(root, bg="#1e1e1e", fg="lime",
                      font=("Arial", 12),
                      selectbackground="gray")
playlist.pack(fill="both", expand=True, padx=10, pady=10)

# Buttons frame
btn_frame = tk.Frame(root, bg="#121212")
btn_frame.pack(pady=5)

tk.Button(btn_frame, text="PLAY", width=8, bg="green", fg="white", command=play_song).grid(row=0, column=0, padx=5)
tk.Button(btn_frame, text="PAUSE", width=8, bg="orange", command=pause_song).grid(row=0, column=1, padx=5)
tk.Button(btn_frame, text="RESUME", width=8, bg="cyan", command=resume_song).grid(row=0, column=2, padx=5)
tk.Button(btn_frame, text="STOP", width=8, bg="red", fg="white", command=stop_song).grid(row=0, column=3, padx=5)

tk.Button(btn_frame, text="<< PREV", width=8, command=prev_song).grid(row=1, column=0, pady=5)
tk.Button(btn_frame, text="NEXT >>", width=8, command=next_song).grid(row=1, column=1, pady=5)
tk.Button(btn_frame, text="ADD SONGS", width=10, command=add_songs).grid(row=1, column=2, pady=5)

shuffle_btn = tk.Button(btn_frame, text="SHUFFLE", width=10, bg="gray", command=toggle_shuffle)
shuffle_btn.grid(row=1, column=3, pady=5)

# Volume
tk.Label(root, text="Volume", bg="#121212", fg="white").pack()
volume_slider = tk.Scale(root, from_=0, to=100, orient="horizontal",
                         bg="#121212", fg="white",
                         command=set_volume)
volume_slider.set(70)
volume_slider.pack(fill="x", padx=20)

root.mainloop()
