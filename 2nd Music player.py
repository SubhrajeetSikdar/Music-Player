import pygame
import tkinter as tkr
from tkinter.filedialog import askdirectory
import os

class MusicPlayer:
    def __init__(self, master):
        self.master = master
        self.master.title("My Music Player")
        self.master.geometry("450x350")
        
        self.directory = askdirectory()
        if not self.directory:
            raise ValueError("No directory selected")
        
        os.chdir(self.directory)
        self.song_list = os.listdir()
        
        self.play_list = tkr.Listbox(self.master, font="Helvetica 12 bold", bg='yellow', selectmode=tkr.SINGLE)
        for item in self.song_list:
            self.play_list.insert(tkr.END, item)
        
        pygame.init()
        pygame.mixer.init()
        
        self.var = tkr.StringVar() 
        self.song_title = tkr.Label(self.master, font="Helvetica 12 bold", textvariable=self.var)
        self.song_title.pack()
        
        self.create_buttons()
        self.play_list.pack(fill="both", expand="yes")
    
    def create_buttons(self):
        buttons_frame = tkr.Frame(self.master)
        buttons_frame.pack(fill="x", pady=10)
        
        self.create_button(buttons_frame, text="PLAY", command=self.play, bg="blue")
        self.create_button(buttons_frame, text="STOP", command=self.stop, bg="red")
        self.create_button(buttons_frame, text="PAUSE", command=self.pause, bg="purple")
        self.create_button(buttons_frame, text="UNPAUSE", command=self.unpause, bg="orange")
        
    def create_button(self, parent, text, command, bg):
        button = tkr.Button(parent, width=8, height=2, font="Helvetica 12 bold", text=text, command=command, bg=bg, fg="white")
        button.pack(side="left", padx=5)
    
    def play(self):
        selected_song = self.play_list.curselection()
        if not selected_song:
            self.var.set("No song selected")
            return
        song_index = selected_song[0]
        song_name = self.play_list.get(song_index)
        pygame.mixer.music.load(song_name)
        self.var.set(song_name)
        pygame.mixer.music.play()
    
    def stop(self):
        pygame.mixer.music.stop()
        self.var.set("Music Stopped")
    
    def pause(self):
        pygame.mixer.music.pause()
        self.var.set("Music Paused")
    
    def unpause(self):
        pygame.mixer.music.unpause()
        self.var.set("Music Resumed")

if __name__ == "__main__":
    music_player = tkr.Tk()
    try:
        player = MusicPlayer(music_player)
        music_player.mainloop()
    except ValueError as e:
        print(e)
