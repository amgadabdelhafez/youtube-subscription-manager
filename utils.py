import os
import json
from datetime import datetime, timedelta
import time
import random
import dateutil.parser
from googleapiclient.errors import HttpError
import csv
import re
import json

MAX_RETRIES = 5
QUOTA_LIMIT = 9000  # Set this to a safe limit below your actual daily quota

# Quota costs for different operations
QUOTA_COST_LIST = 1
QUOTA_COST_CHANNEL = 1
QUOTA_COST_PLAYLIST_ITEMS = 1

def log(message):
    print(f"[LOG] {message}")

def parse_datetime(date_string):
    try:
        return dateutil.parser.parse(date_string)
    except ValueError:
        # If parsing fails, try removing the microseconds
        return datetime.strptime(date_string.split('.')[0], '%Y-%m-%dT%H:%M:%S')

def exponential_backoff(func):
    def wrapper(*args, **kwargs):
        for i in range(MAX_RETRIES):
            try:
                return func(*args, **kwargs)
            except HttpError as e:
                if e.resp.status in [403, 500, 503]:
                    wait_time = (2 ** i) + random.random()
                    log(f"Rate limit hit. Waiting for {wait_time:.2f} seconds.")
                    time.sleep(wait_time)
                else:
                    raise
        log("Max retries reached. Giving up.")
        return None
    return wrapper

def get_quota_usage():
    if os.path.exists('quota_usage.json'):
        with open('quota_usage.json', 'r') as f:
            data = json.load(f)
            if data['date'] == datetime.now().strftime('%Y-%m-%d'):
                return data['usage']
    return 0

def update_quota_usage(usage):
    with open('quota_usage.json', 'w') as f:
        json.dump({
            'date': datetime.now().strftime('%Y-%m-%d'),
            'usage': usage
        }, f)

def reset_quota_if_new_day():
    if os.path.exists('quota_usage.json'):
        with open('quota_usage.json', 'r') as f:
            data = json.load(f)
            if data['date'] != datetime.now().strftime('%Y-%m-%d'):
                update_quota_usage(0)
                log("A new day has started. Quota usage has been reset.")

def check_quota_status():
    reset_quota_if_new_day()
    quota_usage = get_quota_usage()
    if quota_usage >= QUOTA_LIMIT:
        log("Daily quota limit reached.")
        return False
    return True

def estimate_processable_subscriptions(remaining_quota):
    # Estimate based on the cost of listing and fetching details
    estimated_cost_per_subscription = QUOTA_COST_LIST + QUOTA_COST_CHANNEL + QUOTA_COST_PLAYLIST_ITEMS
    return remaining_quota // estimated_cost_per_subscription

def save_progress(last_processed_channel):
    with open('progress.json', 'w') as f:
        json.dump({'last_processed_channel': last_processed_channel}, f)

def load_progress():
    if os.path.exists('progress.json'):
        with open('progress.json', 'r') as f:
            return json.load(f)['last_processed_channel']
    return None



def parse_subscriptions_csv(file_path):
    
    subscriptions = []
    with open(file_path, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            channel_title = row['Channel Title']
            channel_id = row['Channel Id']
            subscriptions.append({
                'title': channel_title,
                'channel_id': channel_id
            })

    return subscriptions