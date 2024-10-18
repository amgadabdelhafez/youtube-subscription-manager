from bs4 import BeautifulSoup
import re
from utils import log
from database import get_last_watch_history_item, store_watch_history_in_db
from datetime import datetime
import signal
import sys
import json

def signal_handler(sig, frame):
    log("Interrupt received, stopping gracefully...")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

def process_watch_history(file_path, account_id, format='html', max_ops=None):
    log(f"Processing watch history from {file_path} for account ID {account_id}...")
    
    last_processed_item = get_last_watch_history_item(account_id)
    items_to_skip = 0 if last_processed_item is None else last_processed_item['index'] + 1
    
    if items_to_skip == 0:
        log("Starting from the beginning of the watch history.")
    else:
        log(f"Continuing from item {items_to_skip} (last processed: {last_processed_item['title']})")
    
    total_processed = items_to_skip
    
    try:
        if format == 'html':
            return process_watch_history_html(file_path, account_id, items_to_skip, max_ops)
        elif format == 'json':
            return process_watch_history_json(file_path, account_id, items_to_skip, max_ops)
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    except KeyboardInterrupt:
        log("Processing interrupted. Saving progress...")
        log(f"Progress saved. Total {total_processed - items_to_skip} items processed.")
        return total_processed - items_to_skip
    except Exception as e:
        log(f"An error occurred while processing watch history: {str(e)}")
        return total_processed - items_to_skip

def process_watch_history_html(file_path, account_id, items_to_skip, max_ops):
    total_processed = items_to_skip
    
    with open(file_path, 'r', encoding='utf-8') as file:
        log(f"File opened successfully: {file_path}")
        content = file.read()
        log(f"Total file size: {len(content)} characters")
        
        soup = BeautifulSoup(content, 'lxml')
        all_items = soup.find_all('div', class_='content-cell mdl-cell mdl-cell--6-col mdl-typography--body-1')
        log(f"Total items found in the file: {len(all_items)}")
        
        for item in all_items[items_to_skip:]:
            total_processed += 1
            
            video_title = item.find('a')
            
            if video_title:
                watch_time = item.find('br').next_sibling.strip()
                url = video_title['href']
                video_id = re.search(r'v=([^&]+)', url)
                channel_id = re.search(r'channel/([^/]+)', url)
                watch_history_item = {
                    'index': total_processed - 1,
                    'title': video_title.text,
                    'url': url,
                    'watch_time': watch_time,
                    'video_id': video_id.group(1) if video_id else None,
                    'channel_id': channel_id.group(1) if channel_id else None,
                    'processed_at': datetime.now().isoformat()
                }
                
                # Store each item immediately
                store_watch_history_in_db([watch_history_item], account_id)
                
                log(f"Processed item {total_processed}: {watch_history_item['title']}")
            else:
                log(f"Skipped item {total_processed}: No video title found")
            
            if total_processed % 10 == 0:
                log(f"Processed {total_processed} items...")
            
            if max_ops and total_processed - items_to_skip >= max_ops:
                log(f"Reached max_ops limit of {max_ops}")
                break

    log(f"Total {total_processed - items_to_skip} watch history items processed for account ID {account_id}.")
    return total_processed - items_to_skip

def process_watch_history_json(file_path, account_id, items_to_skip, max_ops):
    total_processed = items_to_skip
    
    with open(file_path, 'r', encoding='utf-8') as file:
        log(f"File opened successfully: {file_path}")
        content = file.read()
        log(f"Total file size: {len(content)} characters")
        
        watch_history = json.loads(content)
        log(f"Total items found in the file: {len(watch_history)}")
        
        for item in watch_history[items_to_skip:]:
            total_processed += 1
            
            if 'titleUrl' in item:
                watch_history_item = {
                    'index': total_processed - 1,
                    'title': item.get('title', ''),
                    'url': item.get('titleUrl', ''),
                    'watch_time': item.get('time', ''),
                    'video_id': re.search(r'v=([^&]+)', item.get('titleUrl', '')).group(1) if re.search(r'v=([^&]+)', item.get('titleUrl', '')) else None,
                    'channel_id': item['subtitles'][0]['url'].split('/')[-1] if item.get('subtitles') else None,
                    'processed_at': datetime.now().isoformat()
                }
                
                # Store each item immediately
                store_watch_history_in_db([watch_history_item], account_id)
                
                log(f"Processed item {total_processed}: {watch_history_item['title']}")
            else:
                log(f"Skipped item {total_processed}: No video title found")
            
            if total_processed % 10 == 0:
                log(f"Processed {total_processed} items...")
            
            if max_ops and total_processed - items_to_skip >= max_ops:
                log(f"Reached max_ops limit of {max_ops}")
                break

    log(f"Total {total_processed - items_to_skip} watch history items processed for account ID {account_id}.")
    return total_processed - items_to_skip
