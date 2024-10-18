import os
from utils import log
from watch_history import process_watch_history

def handle_watch_history(args, account_id):
    if args.format not in ['html', 'json']:
        log(f"Invalid format '{args.format}' for watch history. Use 'html' or 'json'.")
        return False

    history_file = f"watch-history/{args.account}/Takeout/YouTube and YouTube Music/history/watch-history.{args.format}"
    if not os.path.exists(history_file):
        log(f"Watch history file not found: {history_file}")
        return False

    total_processed = process_watch_history(history_file, account_id, args.format, args.max_ops)
    log(f"Processed {total_processed} watch history items for account {args.account}.")
    return True
