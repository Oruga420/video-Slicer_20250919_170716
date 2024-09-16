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
import requests
import logging
import json
from pydantic import BaseModel
from typing import List, Optional

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,  # Set to DEBUG to capture all log messages
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

# Assistant IDs for OpenAI Assistants API v1
ASSISTANT_IDS = {
    'gpt-4o-mini': 'asst_xzIuTqZSZiWxJRHkPivzvGfx',
    'gpt-4o': 'asst_BvmQwqFWAkxi9npKw2MWa3Kh'
}

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

        print("Generating the voice")  # Print 5: "Generating the voice"

        for idx, chunk in enumerate(chunks, start=1):
            logging.debug(f"Processing text chunk {idx}/{len(chunks)} with length {len(chunk)} characters.")
            # Generate audio without streaming
            audio_chunk = generate(
                text=chunk,
                voice=VOICE_ID,
                model="eleven_multilingual_v2"
            )
            logging.debug(f"Generated audio for chunk {idx}.")
            print("Luna talking")  # Print 6: "Luna talking"
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

def send_to_openai_for_model_selection(user_text):
    # Define the prompt for model selection
    model_selection_prompt = f"""
You are an assistant that decides which model to use for a given user request. Below are the models and their use cases:

- **gpt-4o-mini**: Day-to-day questions and super basic stuff.
- **gpt-4o**: Complex questions that require more elaboration on the response or require compacting information.
- **o1-mini**: For code-related questions but not coding, math questions, things that require logic and feel like they are evaluating your knowledge, for all questions that need reasoning in deep thinking, hard questions.
- **o1-preview**: Only when the sentiment 'think hard' is in the prompt.

User's request:
\"\"\"
{user_text}
\"\"\"

Based on the above, which model should we use for this situation? Only reply with the model name: 'gpt-4o-mini', 'gpt-4o', 'o1-mini', or 'o1-preview'. Do not include any other text.
"""

    print("Message sent to the assistant for model selection:")
    print(model_selection_prompt)

    try:
        logging.info("Determining which model to use using gpt-4o.")
        response = openai.ChatCompletion.create(
            model='gpt-4o',
            messages=[
                {
                    'role': 'user',
                    'content': model_selection_prompt
                }
            ],
            max_tokens=3500,
            temperature=0  # For deterministic output
        )

        assistant_response = response['choices'][0]['message']['content'].strip()
        print("Assistant response for model selection:")
        print(assistant_response)
        logging.debug(f"Assistant response for model selection: {assistant_response}")

        selected_model = assistant_response.lower()

        # Validate the selected model
        valid_models = ['gpt-4o-mini', 'gpt-4o', 'o1-mini', 'o1-preview']
        if selected_model not in valid_models:
            logging.error(f"Invalid model selected: {selected_model}")
            return None, "Invalid model selected."

        # Check for 'think hard' sentiment
        think_hard_phrases = ['think hard', 'deep think', 'deeply think', 'deep thinking']
        think_hard = any(phrase in user_text.lower() for phrase in think_hard_phrases)
        if think_hard and selected_model != 'o1-preview':
            selected_model = 'o1-preview'

        print(f"Using model: {selected_model}")

        return selected_model, None

    except openai.error.OpenAIError as e:
        logging.error(f"Error determining which model to use: {e}")
        return None, "Error determining which model to use."
    except Exception as e:
        logging.error(f"Unexpected error in model selection: {e}")
        return None, "Unexpected error in model selection."

def interact_with_assistant(assistant_id, user_message):
    try:
        headers = {
            'Authorization': f'Bearer {OPENAI_API_KEY}',
            'Content-Type': 'application/json',
            'OpenAI-Beta': 'assistants=v1'
        }

        # Create a new thread
        thread_response = requests.post('https://api.openai.com/v1/threads', headers=headers)
        if thread_response.status_code != 200:
            logging.error(f"Error creating thread: {thread_response.text}")
            return f"Error creating thread: {thread_response.text}"

        thread_id = thread_response.json().get('id')

        # Add the user's message to the thread
        message_data = {
            'role': 'user',
            'content': user_message
        }
        message_response = requests.post(
            f'https://api.openai.com/v1/threads/{thread_id}/messages',
            headers=headers,
            json=message_data
        )
        if message_response.status_code != 200:
            logging.error(f"Error adding message to thread: {message_response.text}")
            return f"Error adding message to thread: {message_response.text}"

        # Run the assistant on the thread
        run_data = {
            'assistant_id': assistant_id
        }
        run_response = requests.post(
            f'https://api.openai.com/v1/threads/{thread_id}/runs',
            headers=headers,
            json=run_data
        )
        if run_response.status_code != 200:
            logging.error(f"Error running assistant on thread: {run_response.text}")
            return f"Error running assistant on thread: {run_response.text}"

        # Wait for the run to complete
        run_id = run_response.json().get('id')
        run_status = run_response.json().get('status')
        while run_status != 'completed':
            time.sleep(1)  # Wait before checking again
            run_status_response = requests.get(
                f'https://api.openai.com/v1/threads/{thread_id}/runs/{run_id}',
                headers=headers
            )
            if run_status_response.status_code != 200:
                logging.error(f"Error checking run status: {run_status_response.text}")
                return f"Error checking run status: {run_status_response.text}"
            run_status = run_status_response.json().get('status')

        # Retrieve messages from the thread
        messages_response = requests.get(
            f'https://api.openai.com/v1/threads/{thread_id}/messages',
            headers=headers
        )
        if messages_response.status_code != 200:
            logging.error(f"Error retrieving messages: {messages_response.text}")
            return f"Error retrieving messages: {messages_response.text}"

        messages = messages_response.json().get('data', [])
        assistant_messages = [msg for msg in messages if msg.get('role') == 'assistant']

        if assistant_messages:
            content_list = assistant_messages[-1].get('content', [])
            assistant_reply = ''
            for item in content_list:
                if isinstance(item, dict) and item.get('type') == 'text':
                    assistant_reply += item.get('text', {}).get('value', '')
                elif isinstance(item, str):
                    assistant_reply += item
            assistant_reply = assistant_reply.strip()
        else:
            logging.error("No response from the assistant.")
            assistant_reply = "No response from the assistant."

        return assistant_reply

    except Exception as e:
        logging.error(f"Unexpected error in interact_with_assistant: {e}")
        return "An error occurred while interacting with the assistant."

def interact_with_chat_completion(model_name, user_message):
    try:
        response = openai.ChatCompletion.create(
            model=model_name,
            messages=[{'role': 'user', 'content': user_message}],
            max_tokens=15000
        )
        assistant_reply = response['choices'][0]['message']['content'].strip()

        return assistant_reply

    except openai.error.OpenAIError as e:
        logging.error(f"OpenAI API error during chat completion: {e}")
        return "An error occurred during chat completion."
    except Exception as e:
        logging.error(f"Unexpected error in interact_with_chat_completion: {e}")
        return "An error occurred during chat completion."

def generate_response(user_text, selected_model):
    try:
        logging.info(f"Generating response using model {selected_model}.")
        print("Message sent to the assistant for response generation:")
        print(f"User: {user_text}")

        if selected_model in ['gpt-4o', 'gpt-4o-mini']:
            assistant_id = ASSISTANT_IDS.get(selected_model)
            if not assistant_id:
                logging.error(f"No assistant ID found for model {selected_model}")
                return "No assistant ID found for the selected model."

            assistant_reply = interact_with_assistant(assistant_id, user_text)

        elif selected_model in ['o1-mini', 'o1-preview']:
            assistant_reply = interact_with_chat_completion(selected_model, user_text)

        else:
            logging.error(f"Invalid model selected: {selected_model}")
            return "Invalid model selected."

        logging.info("Received response from OpenAI.")
        logging.debug(f"Assistant reply: {assistant_reply}")

        print("Assistant response:")
        print(assistant_reply)

        print(f"Luna: {assistant_reply}")
        return assistant_reply

    except Exception as e:
        logging.error(f"Unexpected error in generate_response: {e}")
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

        # Determine which model to use
        selected_model, error = send_to_openai_for_model_selection(user_text)
        if error:
            print(error)
            return

        logging.info("Sending text to assistant.")
        print("Luna's response: ")
        assistant_reply = generate_response(user_text, selected_model)

        if assistant_reply:
            # Parse the assistant's reply into AssistantResponse
            try:
                # Attempt to parse JSON from the response
                assistant_response_json = json.loads(assistant_reply)
                assistant_response = AssistantResponse(**assistant_response_json)
                logging.debug("Assistant response parsed successfully.")
                # Extract only the final_resolution for text-to-speech
                response_content = assistant_response.final_resolution
            except json.JSONDecodeError:
                logging.debug("Assistant response is not in JSON format. Using raw text.")
                # Use the entire response as the content
                response_content = assistant_reply
            except Exception as e:
                logging.error(f"Error parsing assistant response: {e}")
                response_content = "I'm sorry, I didn't understand that."

            save_response_to_file(response_content, user_text)
            # Now process the response text in one go
            process_and_play_text(response_content)

            print("\nReady to listen again! Hold Alt+X to record, release to process.")
            logging.info("Ready for next recording.")
            print("Ready for next message\n")  # Print 7: "Ready for next message"
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