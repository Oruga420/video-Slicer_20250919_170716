import os
import sys
import time
import sounddevice as sd
import soundfile as sf
import numpy as np
import keyboard
import tempfile
import pygame
from elevenlabs import generate, set_api_key
from dotenv import load_dotenv
import threading
import re
import openai
import requests

# Load environment variables
load_dotenv()

# Check and set up API keys
OPENAI_API_KEY = os.getenv('LUNAS_OPENAI_API_KEY')
ELEVEN_LABS_API_KEY = os.getenv('ELEVENLABS_API_KEY')
VOICE_ID = os.getenv('ELEVENLABS_VOICE_ID')
ASSISTANT_ID = os.getenv('OPENAI_ASSISTANT_ID', "asst_BvmQwqFWAkxi9npKw2MWa3Kh")

if not OPENAI_API_KEY or not ELEVEN_LABS_API_KEY or not VOICE_ID:
    print("Error: One or more required environment variables are missing.")
    sys.exit(1)

# Set up OpenAI and Eleven Labs API keys
openai.api_key = OPENAI_API_KEY
set_api_key(ELEVEN_LABS_API_KEY)

recording = None

def play_audio_chunk(audio_chunk):
    pygame.mixer.init()
    with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as temp_file:
        temp_file.write(audio_chunk)
        temp_file_path = temp_file.name

    pygame.mixer.music.load(temp_file_path)
    pygame.mixer.music.play()

    while pygame.mixer.music.get_busy():
        pygame.time.Clock().tick(10)

    pygame.mixer.quit()
    os.unlink(temp_file_path)

def split_into_sentences(text):
    return re.split('(?<=[.!?]) +', text)

def group_sentences(sentences, max_chars=250):
    groups = []
    current_group = []
    current_length = 0

    for sentence in sentences:
        if current_length + len(sentence) > max_chars and current_group:
            groups.append(' '.join(current_group))
            current_group = []
            current_length = 0
        current_group.append(sentence)
        current_length += len(sentence)

    if current_group:
        groups.append(' '.join(current_group))

    return groups

def process_and_play_chunks(text):
    sentences = split_into_sentences(text)
    chunks = group_sentences(sentences)

    for chunk in chunks:
        audio_stream = generate(
            text=chunk,
            voice=VOICE_ID,
            model="eleven_multilingual_v2",
            stream=True
        )
        audio_chunk = b''.join(audio_stream)
        play_audio_chunk(audio_chunk)

def start_recording():
    global recording
    if recording is None:
        print('Start recording...')
        recording = sd.rec(int(44100 * 50), samplerate=44100, channels=2, dtype='int16')

def stop_and_process_recording():
    global recording
    if recording is not None:
        print('Stop recording...')
        sd.stop()
        filename = 'recording.wav'
        sf.write(filename, recording, 44100)
        user_text = transcribe_audio(filename)
        os.remove(filename)
        recording = None
        return user_text
    return None

def transcribe_audio(filename):
    try:
        with open(filename, "rb") as audio_file:
            transcript = openai.Audio.transcribe("whisper-1", audio_file)
        return transcript["text"].strip().lower()
    except Exception as e:
        print(f"Error transcribing audio: {e}")
        return None

def send_to_openai(user_text):
    headers = {
        'Authorization': f'Bearer {OPENAI_API_KEY}',
        'Content-Type': 'application/json',
        'OpenAI-Beta': 'assistants=v1'
    }

    # Create a new thread
    thread_response = requests.post('https://api.openai.com/v1/threads', headers=headers)
    if thread_response.status_code != 200:
        return f"Error creating thread: {thread_response.text}"
    thread_id = thread_response.json().get('id')

    # Add the user's message to the thread
    message_data = {
        'role': 'user',
        'content': user_text
    }
    message_response = requests.post(
        f'https://api.openai.com/v1/threads/{thread_id}/messages',
        headers=headers,
        json=message_data
    )
    if message_response.status_code != 200:
        return f"Error adding message to thread: {message_response.text}"

    # Run the assistant on the thread
    run_data = {
        'assistant_id': ASSISTANT_ID,
        'instructions': "You are Luna, a stoner assistant better than Jarvis from Ironman. We live in Canada, it's 2023. You are THE EFFIN BOMB!! You are presenting. We always be talking MCAE/Pardot any similarities like MCCI or MCEA we are talking about MCAE/Pardot ,,,keep the response short do not say the full response just the letter of the response "
    }
    run_response = requests.post(
        f'https://api.openai.com/v1/threads/{thread_id}/runs',
        headers=headers,
        json=run_data
    )
    if run_response.status_code != 200:
        return f"Error running assistant on thread: {run_response.text}"

    # Wait for the run to complete
    run_id = run_response.json().get('id')
    run_status = run_response.json().get('status')
    while run_status != 'completed':
        run_response = requests.get(
            f'https://api.openai.com/v1/threads/{thread_id}/runs/{run_id}',
            headers=headers
        )
        run_status = run_response.json().get('status')
        time.sleep(1)  # Wait before checking again

    # Retrieve the final response from the assistant
    final_response = requests.get(
        f'https://api.openai.com/v1/threads/{thread_id}/messages',
        headers=headers
    )
    assistant_messages = [msg for msg in final_response.json().get('data', []) if msg.get('role') == 'assistant']
    if assistant_messages:
        return assistant_messages[-1].get('content', [{}])[0].get('text', {}).get('value', '')
    else:
        return "No response from the assistant."

def save_response_to_file(response_text, user_text):
    user_input_words = user_text.split()[:3]
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    file_name = f"{'_'.join(user_input_words)}_{timestamp}.txt"
    
    save_path = r"C:\Users\chuck\OneDrive\Desktop\Dev\luna_cert\luna_cert_chat_monday_like"
    
    if not os.path.exists(save_path):
        os.makedirs(save_path)
    
    full_path = os.path.join(save_path, file_name)
    
    try:
        with open(full_path, "w", encoding="utf-8") as file:
            file.write(response_text)
    except Exception as e:
        print(f"Error saving response to file: {e}")

def process_recording():
    user_text = stop_and_process_recording()
    if user_text:
        print(f"You said: {user_text}")
        print("Luna's response: ")
        openai_response = send_to_openai(user_text)
        
        save_response_to_file(openai_response, user_text)
        
        process_and_play_chunks(openai_response)
        
        print("\nCooling down for 30 seconds...")
        for i in range(30, 0, -1):
            print(f"Resuming in {i} seconds...", end='\r')
            time.sleep(1)
        print("\nReady to listen again! Hold Alt+X to record, release to process.")
    else:
        print("No speech detected or transcription failed. Please try again.")

def main_loop():
    print("Luna is ready! Hold Alt+X to record, release to process.")
    
    keyboard.add_hotkey('alt+x', start_recording)
    keyboard.on_release_key('x', lambda _: process_recording(), suppress=True)

    keyboard.wait()

if __name__ == "__main__":
    main_loop()