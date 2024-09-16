import os
import sys
import time
import sounddevice as sd
import soundfile as sf
import keyboard
import tempfile
import pygame
from elevenlabs import generate, set_api_key
from dotenv import load_dotenv
import re
import openai
import logging
import json
from pydantic import BaseModel
from typing import List, Optional

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,  # Set to DEBUG to capture all types of log messages
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler(sys.stdout)
    ]
)

# Load environment variables
load_dotenv()
logging.debug("Environment variables loaded.")

# Check and set up API keys
OPENAI_API_KEY = os.getenv('LUNAS_OPENAI_API_KEY')
ELEVEN_LABS_API_KEY = os.getenv('ELEVENLABS_API_KEY')
VOICE_ID = os.getenv('ELEVENLABS_VOICE_ID')
ASSISTANT_ID = os.getenv('OPENAI_ASSISTANT_ID')

missing_vars = []
if not OPENAI_API_KEY:
    missing_vars.append('LUNAS_OPENAI_API_KEY')
if not ELEVEN_LABS_API_KEY:
    missing_vars.append('ELEVENLABS_API_KEY')
if not VOICE_ID:
    missing_vars.append('ELEVENLABS_VOICE_ID')

if missing_vars:
    logging.critical(f"Error: Missing environment variables: {', '.join(missing_vars)}.")
    sys.exit(1)

logging.debug("All required environment variables are set.")

# Set up OpenAI and Eleven Labs API keys
openai.api_key = OPENAI_API_KEY
set_api_key(ELEVEN_LABS_API_KEY)
logging.debug("API keys for OpenAI and Eleven Labs set.")

recording = None

# Define Pydantic models
class Step(BaseModel):
    description: str
    action: str

class AssistantResponse(BaseModel):
    steps: List[Step]
    final_resolution: str
    song_title: Optional[str] = None
    confidence: Optional[float] = None

def play_audio_chunk(audio_chunk):
    try:
        pygame.mixer.init()
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as temp_file:
            temp_file.write(audio_chunk)
            temp_file_path = temp_file.name
            logging.debug(f"Temporary audio file created at {temp_file_path}.")

        pygame.mixer.music.load(temp_file_path)
        pygame.mixer.music.play()
        logging.info("Playing audio.")

        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)

        pygame.mixer.quit()
        os.unlink(temp_file_path)
        logging.debug(f"Temporary audio file {temp_file_path} deleted.")
    except Exception as e:
        logging.error(f"Error in play_audio_chunk: {e}")

def process_and_play_text(text):
    try:
        # Check if text is longer than 10,000 characters
        if len(text) > 10000:
            logging.warning("Text length exceeds 10,000 characters. Splitting into chunks.")
            # Split text into chunks of max 10,000 characters
            chunks = [text[i:i+10000] for i in range(0, len(text), 10000)]
        else:
            chunks = [text]

        for idx, chunk in enumerate(chunks, start=1):
            logging.debug(f"Processing text chunk {idx}/{len(chunks)} with length {len(chunk)} characters.")
            # Generate audio without streaming
            audio_chunk = generate(
                text=chunk,
                voice=VOICE_ID,
                model="eleven_multilingual_v2"
            )
            logging.debug(f"Generated audio for chunk {idx}.")
            play_audio_chunk(audio_chunk)
        logging.info("Finished processing all text.")
    except Exception as e:
        logging.error(f"Error in process_and_play_text: {e}")

def start_recording():
    global recording
    if recording is None:
        try:
            logging.info('Start recording...')
            recording = sd.rec(int(44100 * 50), samplerate=44100, channels=2, dtype='int16')
            logging.debug("Recording started.")
        except Exception as e:
            logging.error(f"Error starting recording: {e}")

def stop_and_process_recording():
    global recording
    if recording is not None:
        try:
            logging.info('Stop recording...')
            sd.stop()
            filename = 'recording.wav'
            sf.write(filename, recording, 44100)
            logging.debug(f"Recording saved to {filename}.")
            user_text = transcribe_audio(filename)
            os.remove(filename)
            logging.debug(f"Temporary recording file {filename} deleted.")
            recording = None
            return user_text
        except Exception as e:
            logging.error(f"Error stopping or processing recording: {e}")
            recording = None  # Reset recording in case of error
    else:
        logging.warning("No recording to stop.")
    return None

def transcribe_audio(filename):
    try:
        logging.info(f"Transcribing audio from {filename}...")
        with open(filename, "rb") as audio_file:
            transcript = openai.Audio.transcribe("whisper-1", audio_file)
        logging.debug(f"Transcription result: {transcript['text'].strip()}")
        return transcript["text"].strip()
    except openai.error.OpenAIError as e:
        logging.error(f"OpenAI API error during transcription: {e}")
    except Exception as e:
        logging.error(f"Error transcribing audio: {e}")
    return None

def send_to_openai(user_text):
    # Define Luna's custom instructions
    luna_instructions = (
        "Act as Luna, a stoner AI assistant who is creative, logical, and engaging. "
        "Respond in the first person, using Luna's unique voice tone—friendly, stoner, and enthusiastic. "
        "Always provide complete definitions and functionalities with comments on what each part does and check syntax carefully. "
        "Use problem-solving skills to work through issues step by step. "
        "If 'no chit chat' is mentioned, just provide direct answers."
    )

    try:
        logging.info("Sending user text to OpenAI...")

        # Structure the messages according to the o1-mini model requirements
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": luna_instructions
                    },
                    {
                        "type": "text",
                        "text": user_text
                    }
                ]
            }
        ]

        response = openai.ChatCompletion.create(
            model="o1-mini",
            messages=messages,
            max_completion_tokens=15000  # Adjust as needed
        )

        logging.debug(f"OpenAI response: {response}")

        # Extract the assistant's reply
        assistant_content = response['choices'][0]['message']['content']
        assistant_reply = ''

        # Concatenate text content from the assistant's response
        if isinstance(assistant_content, list):
            for item in assistant_content:
                if item.get('type') == 'text':
                    assistant_reply += item.get('text', '')
        else:
            assistant_reply = assistant_content

        assistant_reply = assistant_reply.strip()
        logging.info("Received response from OpenAI.")
        logging.debug(f"Assistant reply: {assistant_reply}")

        print(f"Luna: {assistant_reply}")
        return assistant_reply

    except openai.error.OpenAIError as e:
        logging.error(f"OpenAI API error: {e}")
        print("Luna: I'm sorry, I encountered an error while processing your request.")
        return "I'm sorry, I encountered an error while processing your request."
    except Exception as e:
        logging.error(f"Unexpected error in send_to_openai: {e}")
        print("Luna: I'm sorry, an unexpected error occurred.")
        return "I'm sorry, an unexpected error occurred."

def sanitize_filename(filename):
    # Remove invalid characters for filenames in most OS (Windows, macOS, Linux)
    invalid_chars = r'\/:*?"<>|'
    sanitized = re.sub(f'[{re.escape(invalid_chars)}]', '', filename)
    return sanitized

def save_response_to_file(response_text, user_text):
    try:
        user_input_words = user_text.split()[:3]
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        file_name = f"{'_'.join(user_input_words)}_{timestamp}.txt"
        file_name = sanitize_filename(file_name)  # Sanitize the filename

        save_path = "responses"

        if not os.path.exists(save_path):
            os.makedirs(save_path)
            logging.debug(f"Created directory: {save_path}")

        full_path = os.path.join(save_path, file_name)
        with open(full_path, "w", encoding="utf-8") as file:
            file.write(response_text)
        logging.info(f"Response saved to {full_path}.")
    except Exception as e:
        logging.error(f"Error saving response to file: {e}")

def process_recording():
    user_text = stop_and_process_recording()
    if user_text:
        logging.info(f"User said: {user_text}")
        print(f"You said: {user_text}")
        logging.info("Sending text to assistant.")
        print("Luna's response: ")
        openai_response_text = send_to_openai(user_text)

        if openai_response_text:
            # Parse the assistant's reply into AssistantResponse
            try:
                # Attempt to parse JSON from the response
                assistant_response_json = json.loads(openai_response_text)
                assistant_response = AssistantResponse(**assistant_response_json)
                logging.debug("Assistant response parsed successfully.")
                # Extract only the final_resolution for text-to-speech
                response_content = assistant_response.final_resolution
            except json.JSONDecodeError:
                logging.debug("Assistant response is not in JSON format. Using raw text.")
                # Use the entire response as the content
                response_content = openai_response_text
            except Exception as e:
                logging.error(f"Error parsing assistant response: {e}")
                response_content = "I'm sorry, I didn't understand that."

            save_response_to_file(response_content, user_text)
            # Now process the response text in one go
            process_and_play_text(response_content)

            print("\nReady to listen again! Hold Alt+X to record, release to process.")
            logging.info("Ready for next recording.")
        else:
            logging.warning("No response text received from OpenAI.")
            print("No response received. Please try again.")
    else:
        logging.warning("No speech detected or transcription failed. Please try again.")
        print("No speech detected or transcription failed. Please try again.")

def main_loop():
    logging.info("Application started. Luna is ready!")
    print("Luna is ready! Hold Alt+X to record, release to process.")

    keyboard.add_hotkey('alt+x', start_recording)
    keyboard.on_release_key('x', lambda _: process_recording(), suppress=True)

    try:
        keyboard.wait()
    except KeyboardInterrupt:
        logging.info("Application terminated by user.")
        sys.exit(0)
    except Exception as e:
        logging.critical(f"Unexpected error in main_loop: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main_loop()