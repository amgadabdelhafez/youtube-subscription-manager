import json
import os

def save_progress(progress_data):
    with open('progress.json', 'w') as f:
        json.dump(progress_data, f)

def load_progress():
    if os.path.exists('progress.json'):
        with open('progress.json', 'r') as f:
            return json.load(f)
    return {'channel_id': None, 'page_token': None}
