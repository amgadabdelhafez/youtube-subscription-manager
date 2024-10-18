import logging
import time
from googleapiclient.errors import HttpError
from progress_tracking import load_progress, save_progress
from database import get_existing_subscriptions, store_subscriptions_in_db, update_database_schema, flag_problematic_subscription

def import_subscriptions(source_youtube, target_youtube, source_account_id, target_account_id, max_ops=None):
    logging.info("Importing subscriptions from source to target account...")
    update_database_schema()  # Ensure the database schema is up to date
    existing_subs_source, subs_source = get_existing_subscriptions(source_account_id)
    existing_subs_target, _ = get_existing_subscriptions(target_account_id)
    last_processed = load_progress()
    
    if last_processed:
        logging.info(f"Resuming import from channel ID: {last_processed}")
    
    if not source_youtube:
        logging.warning("No subscriptions found in the source account.")
        return
    
    subs_to_import = filter_subscriptions(subs_source, existing_subs_target)
    logging.info(f"Found {len(subs_to_import)} new subscriptions to import.")
    
    return process_subscriptions(target_youtube, subs_to_import, source_account_id, target_account_id, max_ops, last_processed)

def filter_subscriptions(subs_source, existing_subs_target):
    return [sub for sub in subs_source if sub['channel_id'] not in existing_subs_target]

def process_subscriptions(target_youtube, subs_to_import, source_account_id, target_account_id, max_ops, last_processed):
    imported_count = 0
    already_subscribed_count = 0
    failed_count = 0
    processed_count = 0
    
    for sub in subs_to_import:
        if max_ops is not None and processed_count >= max_ops:
            logging.info(f"Reached max operations limit ({max_ops}). Stopping import.")
            break

        if last_processed and sub['channel_id'] == last_processed:
            logging.info(f"Resuming from channel: {sub['title']}")
            last_processed = None  # Reset last_processed to continue processing
            continue
        
        logging.info(f"Attempting to import subscription: {sub['title']} (ID: {sub['channel_id']})")
        result = import_subscription(target_youtube, sub)
        
        if result == 'success':
            imported_count += 1
        elif result == 'already_subscribed':
            already_subscribed_count += 1
        else:
            failed_count += 1
            flag_problematic_subscription(source_account_id, sub['channel_id'], result)
        
        logging.info(f"Storing subscription in database: {sub['title']} (ID: {sub['channel_id']})")
        store_subscriptions_in_db([sub], source_account_id)
        logging.info(f"Updated database for {sub['title']} in source account.")
        
        save_progress(sub['channel_id'])
        processed_count += 1
        
        if processed_count % 10 == 0:
            logging.info(f"Progress: Processed {processed_count} out of {len(subs_to_import)} subscriptions")
        
        time.sleep(1)  # Add a delay to avoid hitting rate limits
    
    logging.info("Subscription import completed.")
    logging.info(f"Total processed: {processed_count}")
    logging.info(f"Successfully imported: {imported_count}")
    logging.info(f"Already subscribed: {already_subscribed_count}")
    logging.info(f"Failed to import: {failed_count}")
    
    return {
        'processed': processed_count,
        'imported': imported_count,
        'already_subscribed': already_subscribed_count,
        'failed': failed_count
    }

def import_subscription(target_youtube, sub):
    max_retries = 3
    retry_delay = 5  # seconds

    for attempt in range(max_retries):
        try:
            logging.info(f"Attempt {attempt + 1} to subscribe to {sub['title']} (ID: {sub['channel_id']})")
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
            logging.info(f"Successfully subscribed to {sub['title']} in target account.")
            return 'success'
        except HttpError as e:
            if e.resp.status == 400 and 'subscriptionDuplicate' in str(e):
                logging.info(f"Already subscribed to {sub['title']} in target account.")
                return 'already_subscribed'
            elif e.resp.status == 404:
                logging.warning(f"Channel not found for {sub['title']} (ID: {sub['channel_id']}). It may have been deleted or made private.")
                return 'channel_not_found'
            elif attempt < max_retries - 1:
                logging.warning(f"Failed to subscribe to {sub['title']} (ID: {sub['channel_id']}). Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                logging.error(f"Failed to subscribe to {sub['title']} (ID: {sub['channel_id']}) after {max_retries} attempts: {e}")
                return 'subscription_failed'
        except Exception as e:
            logging.error(f"Unexpected error while subscribing to {sub['title']} (ID: {sub['channel_id']}): {e}")
            return 'unexpected_error'

    return 'subscription_failed'
