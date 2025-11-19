import json
import os
import random
import datetime
from pathlib import Path
import exifread
from tkinter import Tk, Label
from PIL import Image, ImageTk, ImageOps, ImageDraw, ImageFont
import spotipy
from spotipy.oauth2 import SpotifyOAuth

import credentials

SONG_START_MS = 30000

def get_year_week(dt):
    year, week, _ = dt.isocalendar()
    return (year, week)

def load_spotify_history(folder):
    tracks_by_week = {}

    for file in Path(folder).glob('Streams*.json'):
        with open(file, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                print(f'Skipping invalid JSON file: {file}')
                continue

        if isinstance(data, dict):
            possible_list_keys = ['streaming_history', 'playback', 'plays']
            for key in possible_list_keys:
                if key in data and isinstance(data[key], list):
                    data = data[key]
                    break

        if not isinstance(data, list):
            print(f'Skipping unexpected format in file: {file}')
            continue

        for entry in data:
            if 'ts' not in entry:
                continue
            try:
                dt = datetime.datetime.strptime(entry['ts'], '%Y-%m-%dT%H:%M:%SZ')
            except ValueError:
                try:
                    dt = datetime.datetime.fromisoformat(entry['ts'].replace('Z', '+00:00'))
                except Exception as e:
                    print(f'Failed to parse timestamp: {e}')

            year_week = get_year_week(dt)

            track_name = entry.get('master_metadata_track_name')
            artist_name = entry.get('master_metadata_album_artist_name')

            if track_name is None or artist_name is None:
                track_name = track_name or entry.get('episode_name') or 'Unknown Track'
                artist_name = artist_name or entry.get('episode_show_name') or 'Unknown Artist'

            tracks_by_week.setdefault(year_week, []).append({
                'artist': artist_name,
                'track': track_name,
                'timestamp': dt,
                'ms_played': entry.get('ms_played', None),
                'uri': entry.get('spotify_track_uri')
            })

    return tracks_by_week

def get_photo_date(path):
    try:
        with open(path, 'rb') as f:
            tags = exifread.process_file(f, stop_tag='EXIF DateTimeOriginal')

        if 'EXIF DateTimeOriginal' in tags:
            datestr = str(tags['EXIF DateTimeOriginal'])
            return datetime.datetime.strptime(datestr, '%Y:%m:%d %H:%M:%S')
    except Exception:
        pass

    ts = os.path.getmtime(path)
    return datetime.datetime.fromtimestamp(ts)

def load_photos(folder):
    photos_by_week = {}
    for imgfile in Path(folder).glob('*.*'):
        if imgfile.suffix.lower() not in ['.jpg', '.jpeg']:
            continue
        dt = get_photo_date(imgfile)
        yw = get_year_week(dt)
        photos_by_week.setdefault(yw, []).append(str(imgfile))

    return photos_by_week

def get_exif_date(path):
    img = Image.open(path)
    exif = img.getexif()
    date_tag = 36867  # DateTimeOriginal
    return exif.get(date_tag)

class MemoryMachine:
    def __init__(self, max_w=1400, max_h=900):
        self.max_w = max_w
        self.max_h = max_h

        self.root = Tk()
        self.root.title('Memory Machine')
        self.label = Label(self.root)
        self.label.pack()

        self.root.bind('<space>', self.next_item)
        self.root.bind('<Button-1>', self.next_item)

        self.sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
            client_id = credentials.spotipy_client_id,
            client_secret = credentials.spotipy_secret_id,
            redirect_uri = 'http://127.0.0.1:8080/callback',
            scope = 'user-modify-playback-state,user-read-playback-state'
        ))

        self.next_item()

        self.root.mainloop()
        self.root.after(500, lambda: self.root.attributes('-topmost', False))

    def next_item(self, event=None):
        track, photo, week = get_random_photo_and_song(tracks, photos)
        self.current_track = track  
        self.current_photo = photo
        self.current_week = week
        self.play_audio(track['uri'], position_ms=SONG_START_MS)
        self.show_image(photo)

    def show_image(self, path):
        img = Image.open(path)
        img = ImageOps.exif_transpose(img)

        scale = min(self.max_w / img.width, self.max_h / img.height)
        if scale < 1:
            new_size = (int(img.width * scale), int(img.height * scale))
            img = img.resize(new_size, Image.LANCZOS)

        draw = ImageDraw.Draw(img)
        title = self.current_track.get('track', '')
        artist = self.current_track.get('artist', '')
        song_text = f"{title} — {artist}"
        date_taken = get_exif_date(path)

        font = ImageFont.truetype('/System/Library/Fonts/Supplemental/Menlo.ttc', 24)

        bbox = draw.textbbox((0, 0), song_text, font=font)
        text_width = bbox[2] - bbox[0]
        draw.text(((img.width - text_width) / 2, 30), song_text, fill='white', font=font)

        date_text = str(date_taken)
        bbox = draw.textbbox((0, 0), date_text, font=font)
        text_width = bbox[2] - bbox[0]
        draw.text((img.width - text_width - 30, 30), date_text, fill='white', font=font)

        self.tk_img = ImageTk.PhotoImage(img)
        self.label.config(image=self.tk_img)
    
    def play_audio(self, spotify_uri, position_ms):
        devices = self.sp.devices()
        if not devices or not devices['devices']:
            print('No active Spotify devices. Try opening Spotify on your computer or phone and playing a song.')
            return

        device_id = devices['devices'][0]['id']

        self.sp.start_playback(
            device_id=device_id,
            uris=[spotify_uri],
            position_ms=position_ms
        )

def get_random_photo_and_song(tracks, photos):
    common_weeks = list(set(tracks.keys()) & set(photos.keys()))
    week = random.choice(common_weeks)
    track = random.choice(tracks[week])
    photo = random.choice(photos[week])
    return track, photo, week


if __name__ == '__main__':
    spotify_dir = '/Users/emersonlange/Desktop/fun/SpotifyHistory/'
    photos_dir = '/Users/emersonlange/Desktop/fun/phone_photo_archive/'
    tracks = load_spotify_history(spotify_dir)
    photos = load_photos(photos_dir)
    
    MemoryMachine()



