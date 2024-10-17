import os
import sqlite3
import sys
import json
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import time
import dateutil.parser
import random
import argparse
from bs4 import BeautifulSoup
import traceback
import re

# Define the scope for YouTube Data API
SCOPES = ['https://www.googleapis.com/auth/youtube.force-ssl']
MAX_RETRIES = 5
QUOTA_LIMIT = 9000  # Set this to a safe limit below your actual daily quota

# Quota costs for different operations
QUOTA_COST_LIST = 1
QUOTA_COST_CHANNEL = 1
QUOTA_COST_PLAYLIST_ITEMS = 1
# Note: subscriptions.insert costs 50 units, but we're not using it in this script currently

def log(message):
    print(f"[LOG] {message}")

def authenticate_youtube(account_type):
    creds = None
    token_file = f'token_{account_type}.json'
    client_secret_file = f'client_secret_{account_type}.json'
    log(f"Authenticating {account_type} account...")
    if os.path.exists(token_file):
        log(f"Token file found. Loading credentials...")
        creds = Credentials.from_authorized_user_file(token_file, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            log("Refreshing expired credentials...")
            creds.refresh(Request())
        else:
            log(f"Starting new authentication flow for {account_type} account...")
            flow = InstalledAppFlow.from_client_secrets_file(client_secret_file, SCOPES)
            creds = flow.run_local_server(port=0)
        log(f"Saving new credentials to {token_file}...")
        with open(token_file, 'w') as token:
            token.write(creds.to_json())
    log(f"Authentication for {account_type} account completed.")
    return build('youtube', 'v3', credentials=creds)

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

@exponential_backoff
def get_channel_details(youtube, channel_id):
    try:
        response = youtube.channels().list(
            part="snippet,statistics,contentDetails",
            id=channel_id
        ).execute()
        
        if 'items' in response and len(response['items']) > 0:
            channel = response['items'][0]
            snippet = channel['snippet']
            statistics = channel['statistics']
            content_details = channel['contentDetails']
            
            created_at = snippet['publishedAt']
            total_videos = statistics.get('videoCount', 'N/A')
            
            # Get the last video upload date
            playlist_id = content_details['relatedPlaylists']['uploads']
            last_upload_date = 'N/A'
            try:
                last_video = youtube.playlistItems().list(
                    part="snippet",
                    playlistId=playlist_id,
                    maxResults=1
                ).execute()
                
                if 'items' in last_video and len(last_video['items']) > 0:
                    last_upload_date = last_video['items'][0]['snippet']['publishedAt']
            except HttpError as e:
                if e.resp.status == 404:
                    log(f"Playlist not found for channel {channel_id}. Skipping last upload date.")
                else:
                    raise
            
            # Calculate upload frequency (very rough estimate)
            if last_upload_date != 'N/A' and total_videos != 'N/A':
                start_date = parse_datetime(created_at)
                end_date = parse_datetime(last_upload_date)
                days_active = (end_date - start_date).days
                if days_active > 0:
                    upload_frequency = float(total_videos) / days_active
                else:
                    upload_frequency = 0
            else:
                upload_frequency = 0
            
            return {
                'created_at': created_at,
                'total_videos': total_videos,
                'last_upload_date': last_upload_date,
                'upload_frequency': f"{upload_frequency:.2f} videos per day"
            }
        else:
            return None
    except HttpError as e:
        log(f"An error occurred while fetching channel details for {channel_id}: {e}")
        return None

def update_database_schema(db_name="subscriptions.db"):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    try:
        # Check if the subscriptions table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='subscriptions'")
        if cursor.fetchone() is None:
            # If the table doesn't exist, create it with all columns
            cursor.execute('''CREATE TABLE subscriptions 
                              (channel_id TEXT PRIMARY KEY, 
                               title TEXT, 
                               description TEXT, 
                               published_at TEXT, 
                               created_at TEXT,
                               total_videos TEXT,
                               last_upload_date TEXT,
                               upload_frequency TEXT,
                               source_account INTEGER, 
                               target_account INTEGER)''')
        else:
            # If the table exists, check for missing columns and add them
            columns_to_add = [
                ('created_at', 'TEXT'),
                ('total_videos', 'TEXT'),
                ('last_upload_date', 'TEXT'),
                ('upload_frequency', 'TEXT'),
                ('source_account', 'INTEGER'),
                ('target_account', 'INTEGER')
            ]
            for column, dtype in columns_to_add:
                try:
                    cursor.execute(f"ALTER TABLE subscriptions ADD COLUMN {column} {dtype}")
                except sqlite3.OperationalError:
                    # Column already exists, skip
                    pass
        
        # Check if the watch_history table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='watch_history'")
        if cursor.fetchone() is None:
            # If the table doesn't exist, create it
            cursor.execute('''CREATE TABLE watch_history 
                              (id INTEGER PRIMARY KEY AUTOINCREMENT,
                               title TEXT,
                               url TEXT,
                               watch_time TEXT,
                               video_id TEXT,
                               channel_id TEXT)''')
        
        conn.commit()
        log("Database schema updated successfully.")
    except sqlite3.Error as e:
        log(f"An error occurred while updating the database schema: {e}")
    finally:
        conn.close()

def get_existing_subscriptions(db_name="subscriptions.db"):
    update_database_schema(db_name)
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    existing_subs = {}
    try:
        cursor.execute("SELECT channel_id, last_upload_date FROM subscriptions")
        for row in cursor.fetchall():
            existing_subs[row[0]] = row[1]
    except sqlite3.Error as e:
        log(f"An error occurred while fetching existing subscriptions: {e}")
    finally:
        conn.close()
    return existing_subs

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

def list_subscriptions(youtube, existing_subs, max_ops=None):
    log("Listing subscriptions...")
    if not check_quota_status():
        return []

    request = youtube.subscriptions().list(
        part="snippet",
        mine=True,
        maxResults=50
    )
    subscriptions = []
    quota_usage = get_quota_usage()
    
    try:
        while request and (max_ops is None or len(subscriptions) < max_ops):
            if not check_quota_status():
                break

            log("Executing API request...")
            response = request.execute()
            log(f"API response received. Status: {response.get('kind', 'Unknown')}")
            
            quota_usage += QUOTA_COST_LIST
            update_quota_usage(quota_usage)

            if 'items' not in response:
                log(f"Unexpected API response: {response}")
                break

            for item in response['items']:
                if max_ops is not None and len(subscriptions) >= max_ops:
                    break

                channel_id = item['snippet']['resourceId']['channelId']
                channel_info = {
                    'channel_id': channel_id,
                    'title': item['snippet']['title'],
                    'description': item['snippet']['description'],
                    'published_at': item['snippet']['publishedAt']
                }
                
                log(f"Processing channel: {channel_info['title']} ({channel_id})")
                
                # Check if we need to update the channel details
                if channel_id not in existing_subs or (
                    existing_subs[channel_id] != 'N/A' and
                    existing_subs[channel_id] is not None and
                    parse_datetime(existing_subs[channel_id]) < datetime.now() - timedelta(days=7)
                ):
                    if not check_quota_status():
                        break
                    # Get additional channel details
                    details = get_channel_details(youtube, channel_id)
                    if details:
                        channel_info.update(details)
                        quota_usage += QUOTA_COST_CHANNEL + QUOTA_COST_PLAYLIST_ITEMS
                        update_quota_usage(quota_usage)
                
                subscriptions.append(channel_info)
                save_progress(channel_id)
                time.sleep(2)  # Add a delay to avoid hitting rate limits
            
            if not check_quota_status() or (max_ops is not None and len(subscriptions) >= max_ops):
                break
            request = youtube.subscriptions().list_next(request, response)
    except HttpError as e:
        if e.resp.status == 403 and 'quotaExceeded' in str(e):
            log("Quota exceeded. Stopping the process.")
        else:
            log(f"An error occurred while listing subscriptions: {e}")
            log(f"Error details: {traceback.format_exc()}")
    except Exception as e:
        log(f"An unexpected error occurred: {str(e)}")
        log(f"Error details: {traceback.format_exc()}")
    except KeyboardInterrupt:
        log("Script interrupted. Saving progress...")
    
    log(f"Found {len(subscriptions)} subscriptions.")
    return subscriptions

def store_subscriptions_in_db(subscriptions, account_type, db_name="subscriptions.db"):
    log(f"Storing {len(subscriptions)} subscriptions for {account_type} account in {db_name}...")
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    updated_channels = []
    
    try:
        # Insert or update the subscriptions
        for sub in subscriptions:
            cursor.execute('''INSERT OR REPLACE INTO subscriptions 
                              (channel_id, title, description, published_at, 
                               created_at, total_videos, last_upload_date, upload_frequency,
                               source_account, target_account) 
                              VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 
                                      COALESCE((SELECT target_account FROM subscriptions WHERE channel_id = ?), ?))''', 
                           (sub['channel_id'], sub['title'], sub['description'], 
                            sub['published_at'], sub.get('created_at', 'N/A'), 
                            sub.get('total_videos', 'N/A'), sub.get('last_upload_date', 'N/A'),
                            sub.get('upload_frequency', 'N/A'),
                            1 if account_type == 'source' else 0,
                            sub['channel_id'],
                            1 if account_type == 'target' else 0))
            updated_channels.append(sub['channel_id'])
        
        conn.commit()
        log(f"Subscriptions for {account_type} account stored in database.")
    except sqlite3.Error as e:
        log(f"An error occurred while storing subscriptions: {e}")
    finally:
        conn.close()
    
    return updated_channels

def save_progress(last_processed_channel):
    with open('progress.json', 'w') as f:
        json.dump({'last_processed_channel': last_processed_channel}, f)

def load_progress():
    if os.path.exists('progress.json'):
        with open('progress.json', 'r') as f:
            return json.load(f)['last_processed_channel']
    return None

def import_subscriptions(source_youtube, target_youtube, max_ops=None):
    log("Importing subscriptions from source to target account...")
    existing_subs = get_existing_subscriptions()
    source_subscriptions = list_subscriptions(source_youtube, existing_subs, max_ops)
    
    if not source_subscriptions:
        log("No subscriptions found in the source account.")
        return
    
    for sub in source_subscriptions:
        try:
            target_youtube.subscriptions().insert(
                part="snippet",
                body={
                    "snippet": {
                        "resourceId": {
                            "kind": "youtube#channel",
                            "channelId": sub['channel_id']
                        }
                    }
                }
            ).execute()
            log(f"Subscribed to {sub['title']} in target account.")
        except HttpError as e:
            if e.resp.status == 400 and 'subscriptionDuplicate' in str(e):
                log(f"Already subscribed to {sub['title']} in target account.")
            else:
                log(f"Failed to subscribe to {sub['title']}: {e}")
        
        time.sleep(1)  # Add a delay to avoid hitting rate limits
    
    log("Subscription import completed.")





def process_watch_history(file_path, max_ops=None):
    log(f"Processing watch history from {file_path}...")
    watch_history = []
    with open(file_path, 'r', encoding='utf-8') as file:
        chunk_size = 1024 * 1024  # 1MB chunks
        while len(watch_history) < max_ops:
            chunk = file.read(chunk_size)
            if not chunk:
                break
            watch_history = process_chunk(chunk, max_ops)

        log(f"Total {len(watch_history)} watch history items.")
        return watch_history

def process_chunk(chunk, max_ops):
    soup = BeautifulSoup(chunk, 'html.parser')
    # Process the chunk here
    # For example: find specific tags or extract data    
    watch_history = []
    for item in soup.find_all('div', class_='content-cell mdl-cell mdl-cell--6-col mdl-typography--body-1'):
        if max_ops is not None and len(watch_history) >= max_ops:
            break
        video_title = item.find('a')
        if video_title:
            watch_time = item.find('br').next_sibling.strip()
            url = video_title['href']
            video_id = re.search(r'v=([^&]+)', url)
            channel_id = re.search(r'channel/([^/]+)', url)
            watch_history.append({
                'title': video_title.text,
                'url': url,
                'watch_time': watch_time,
                'video_id': video_id.group(1) if video_id else None,
                'channel_id': channel_id.group(1) if channel_id else None
            })
    
    log(f"Processed chunk complete, {len(watch_history)} watch history items processed.")
    return watch_history

def store_watch_history_in_db(watch_history, db_name="subscriptions.db"):
    log(f"Storing {len(watch_history)} watch history items in {db_name}...")
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    
    try:
        cursor.executemany('''INSERT OR REPLACE INTO watch_history 
                              (title, url, watch_time, video_id, channel_id) 
                              VALUES (?, ?, ?, ?, ?)''', 
                           [(item['title'], item['url'], item['watch_time'], 
                             item['video_id'], item['channel_id']) for item in watch_history])
        
        conn.commit()
        log(f"Watch history stored in database.")
    except sqlite3.Error as e:
        log(f"An error occurred while storing watch history: {e}")
    finally:
        conn.close()

def main():
    parser = argparse.ArgumentParser(description="YouTube Subscription Manager")
    parser.add_argument('mode', choices=['update', 'import', 'history'],
                        help="Mode of operation: update DB, import subscriptions, or process watch history")
    parser.add_argument('--history-file', help="Path to the watch-history.html file (required for 'history' mode)")
    parser.add_argument('--max-ops', type=int, help="Maximum number of operations to perform")
    args = parser.parse_args()

    try:
        if args.mode == 'update':
            reset_quota_if_new_day()
            quota_usage = get_quota_usage()
            remaining_quota = max(0, QUOTA_LIMIT - quota_usage)

            if not check_quota_status():
                next_reset = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
                log("Quota limit reached. Please try again tomorrow when the quota resets.")
                log(f"Next quota reset: {next_reset.strftime('%Y-%m-%d %H:%M:%S')} (in {(next_reset - datetime.now()).total_seconds() / 3600:.2f} hours)")
                log(f"If you need to process more subscriptions, consider increasing your quota limit.")
                log("Visit https://developers.google.com/youtube/v3/getting-started#quota for more information.")
                return

            estimated_processable = estimate_processable_subscriptions(remaining_quota)
            log(f"Estimated number of subscriptions that can be processed with remaining quota: {estimated_processable}")

            youtube_source = authenticate_youtube('source')
            existing_subs = get_existing_subscriptions()
            last_processed = load_progress()
            
            if last_processed:
                log(f"Resuming from channel ID: {last_processed}")
            
            source_subscriptions = list_subscriptions(youtube_source, existing_subs, args.max_ops)
            
            if not source_subscriptions:
                log("No subscriptions found or processed in the source account. This could be due to quota limitations.")
                return
            
            updated_channels = store_subscriptions_in_db(source_subscriptions, 'source')
            
            log("\n--- Summary ---")
            log(f"Total subscriptions processed: {len(source_subscriptions)}")
            log(f"Updated or new channels: {len(updated_channels)}")
            
        elif args.mode == 'import':
            youtube_source = authenticate_youtube('source')
            youtube_target = authenticate_youtube('target')
            import_subscriptions(youtube_source, youtube_target, args.max_ops)
        
        elif args.mode == 'history':
            if not args.history_file:
                log("Error: --history-file is required for 'history' mode")
                return
            watch_history = process_watch_history(args.history_file, args.max_ops)
            store_watch_history_in_db(watch_history)
            log(f"Processed and stored {len(watch_history)} watch history items.")
        
    except Exception as e:
        log(f"An unexpected error occurred: {str(e)}")
        log(f"Error details: {traceback.format_exc()}")
    finally:
        quota_usage = get_quota_usage()
        remaining_quota = max(0, QUOTA_LIMIT - quota_usage)
        log(f"Total quota usage: {quota_usage}")
        log(f"Remaining quota: {remaining_quota}")
        if quota_usage >= QUOTA_LIMIT:
            next_reset = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
            log(f"Quota limit reached. The script will be able to process more subscriptions after the next reset.")
            log(f"Next quota reset: {next_reset.strftime('%Y-%m-%d %H:%M:%S')} (in {(next_reset - datetime.now()).total_seconds() / 3600:.2f} hours)")
        else:
            estimated_remaining = estimate_processable_subscriptions(remaining_quota)
            log(f"Estimated number of additional subscriptions that can be processed: {estimated_remaining}")

if __name__ == '__main__':
    main()
