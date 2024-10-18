from googleapiclient.errors import HttpError
import time
from utils import log
from progress_tracking import load_progress, save_progress
from database import get_existing_subscriptions, store_subscriptions_in_db

def import_subscriptions(source_youtube, target_youtube, source_account_id, target_account_id, max_ops=None):
    log("Importing subscriptions from source to target account...")
    existing_subs_source, subs_source = get_existing_subscriptions(source_account_id)
    existing_subs_target, _ = get_existing_subscriptions(target_account_id)
    last_processed = load_progress()
    
    if last_processed:
        log(f"Resuming import from channel ID: {last_processed}")
    
    if not source_youtube:
        log("No subscriptions found in the source account.")
        return
    
    subs_to_import = filter_subscriptions(subs_source, existing_subs_target)
    log(f"Found {len(subs_to_import)} new subscriptions to import.")
    
    process_subscriptions(target_youtube, subs_to_import, source_account_id, target_account_id, max_ops, last_processed)

def filter_subscriptions(subs_source, existing_subs_target):
    return [sub for sub in subs_source if sub['channel_id'] not in existing_subs_target]

def process_subscriptions(target_youtube, subs_to_import, source_account_id, target_account_id, max_ops, last_processed):
    imported_count = 0
    processed_count = 0
    for sub in subs_to_import:
        if max_ops is not None and processed_count >= max_ops:
            log(f"Reached max operations limit ({max_ops}). Stopping import.")
            break

        if last_processed and sub['channel_id'] == last_processed:
            log(f"Resuming from channel: {sub['title']}")
            last_processed = None  # Reset last_processed to continue processing
            continue
        
        if import_subscription(target_youtube, sub):
            imported_count += 1
        
        store_subscriptions_in_db([sub], source_account_id, target_account_id, 'import')
        log(f"Updated database for {sub['title']} in target account.")
        
        save_progress(sub['channel_id'])
        processed_count += 1
        time.sleep(1)  # Add a delay to avoid hitting rate limits
    
    log(f"Subscription import completed. Processed {processed_count} subscriptions, {imported_count} new subscriptions added to YouTube.")

def import_subscription(target_youtube, sub):
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
        return True
    except HttpError as e:
        if e.resp.status == 400 and 'subscriptionDuplicate' in str(e):
            log(f"Already subscribed to {sub['title']} in target account.")
        else:
            log(f"Failed to subscribe to {sub['title']}: {e}")
        return False
