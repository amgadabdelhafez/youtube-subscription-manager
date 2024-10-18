import os
from datetime import datetime, timedelta
from auth import authenticate_youtube
from database import get_existing_subscriptions, store_subscriptions_in_db
from youtube_api import list_subscriptions, import_subscriptions
from quota_management import check_quota_status, get_remaining_quota, estimate_processable_subscriptions, log_quota_information, can_perform_operation
from progress_tracking import load_progress
from utils import log, parse_subscriptions_csv

def handle_subscriptions(args, account_id):
    if args.format == 'csv':
        return handle_csv_subscriptions(args, account_id)
    elif args.format == 'api':
        return handle_api_subscriptions(args, account_id)
    else:
        log(f"Invalid format '{args.format}' for subscriptions. Use 'api' or 'csv'.")
        return False

def handle_csv_subscriptions(args, account_id):
    csv_file = f"watch-history/{args.account}/Takeout/YouTube and YouTube Music/subscriptions/subscriptions.csv"
    if not os.path.exists(csv_file):
        log(f"Subscriptions CSV file not found: {csv_file}")
        return False
    subscriptions = parse_subscriptions_csv(csv_file)
    updated_channels = store_subscriptions_in_db(subscriptions, account_id, 'csv')
    log(f"Imported {len(subscriptions)} subscriptions from CSV file.")
    log(f"Updated or new channels: {len(updated_channels)}")
    return True

def handle_api_subscriptions(args, account_id):
    if not can_perform_operation('SEARCH'):
        log_quota_limit_reached()
        return False

    remaining_quota = get_remaining_quota()
    estimated_processable = estimate_processable_subscriptions()
    log(f"Estimated number of subscriptions that can be processed with remaining quota: {estimated_processable}")

    existing_subs, _ = get_existing_subscriptions(account_id)
    log(f"Existing subscriptions: {len(existing_subs)}")
    
    youtube_source = authenticate_youtube(args.account)
    source_subscriptions = list_subscriptions(youtube_source, existing_subs, args.account, args.max_ops)
    
    if not source_subscriptions:
        log("No subscriptions found or processed in the source account. This could be due to quota limitations.")
        return False
    
    log(f"Fetched {len(source_subscriptions)} subscriptions from YouTube API")
    
    updated_channels = store_subscriptions_in_db(source_subscriptions, account_id)
    
    log("\n--- Summary ---")
    log(f"Total subscriptions processed: {len(source_subscriptions)}")
    log(f"Updated or new channels: {len(updated_channels)}")
    
    log("Details of updated channels:")
    for channel in updated_channels:
        log(f"- {channel}")
    
    log_quota_information()
    
    return True

def handle_import_subscriptions(args, source_account_id, target_account_id):
    youtube_source = authenticate_youtube(args.from_account)
    youtube_target = authenticate_youtube(args.to_account)
    import_subscriptions(youtube_source, youtube_target, source_account_id, target_account_id, args.max_ops)

def log_quota_limit_reached():
    next_reset = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    log("Quota limit reached. Please try again tomorrow when the quota resets.")
    log(f"Next quota reset: {next_reset.strftime('%Y-%m-%d %H:%M:%S')} (in {(next_reset - datetime.now()).total_seconds() / 3600:.2f} hours)")
    log(f"If you need to process more subscriptions, consider increasing your quota limit.")
    log("Visit https://developers.google.com/youtube/v3/getting-started#quota for more information.")
