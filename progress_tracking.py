import json
import os
from utils import log

def save_progress(progress_data):
    with open('progress.json', 'w') as f:
        json.dump(progress_data, f)

def load_progress():
    default_progress = {'channel_id': None, 'page_token': None}
    if os.path.exists('progress.json'):
        try:
            with open('progress.json', 'r') as f:
                progress = json.load(f)
            if isinstance(progress, dict) and 'channel_id' in progress and 'page_token' in progress:
                log("Progress loaded successfully.")
                return progress
            else:
                log("Invalid progress data format. Using default progress.")
        except json.JSONDecodeError:
            log("Error decoding progress.json. Using default progress.")
        except Exception as e:
            log(f"Unexpected error loading progress: {str(e)}. Using default progress.")
    else:
        log("No progress file found. Starting from the beginning.")
    return default_progress
