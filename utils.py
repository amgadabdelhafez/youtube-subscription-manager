import logging
from datetime import datetime
import time
import random
import csv
from googleapiclient.errors import HttpError

MAX_RETRIES = 5

def log(message):
    logging.info(message)

def parse_datetime(date_string):
    try:
        return datetime.strptime(date_string, '%Y-%m-%dT%H:%M:%S.%fZ')
    except ValueError:
        return datetime.strptime(date_string, '%Y-%m-%dT%H:%M:%SZ')

def exponential_backoff(func):
    def wrapper(*args, **kwargs):
        for i in range(MAX_RETRIES):
            try:
                return func(*args, **kwargs)
            except HttpError as e:
                if e.resp.status in [403, 500, 503]:
                    wait_time = (2 ** i) + random.random()
                    logging.warning(f"Rate limit hit. Waiting for {wait_time:.2f} seconds.")
                    time.sleep(wait_time)
                else:
                    raise
        logging.error("Max retries reached. Giving up.")
        return None
    return wrapper

def parse_subscriptions_csv(csv_file):
    subscriptions = []
    with open(csv_file, 'r', encoding='utf-8') as file:
        csv_reader = csv.DictReader(file)
        for row in csv_reader:
            subscription = {
                'channel_id': row.get('Channel Id', ''),
                'channel_title': row.get('Channel Title', ''),
                'channel_url': row.get('Channel Url', ''),
            }
            subscriptions.append(subscription)
    return subscriptions
