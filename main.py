import logging
from datetime import datetime, timedelta
import traceback
from auth import authenticate_youtube
from database import update_database_schema
from quota_management import get_quota_usage, get_actual_quota, estimate_processable_subscriptions, log_quota_information, load_quota_details, save_quota_details
from utils import log
from cli import parse_arguments
from account_management import get_available_accounts, setup_accounts
from subscription_management import handle_subscriptions, handle_import_subscriptions
from watch_history import get_watch_history, print_watch_history

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        filename='youtube_subscription_manager.log',
        filemode='a'
    )
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    console.setFormatter(formatter)
    logging.getLogger('').addHandler(console)

def main():
    setup_logging()
    args = parse_arguments()

    try:
        logging.info("Starting YouTube Subscription Manager")
        # Load quota details at the start of the script
        load_quota_details()

        update_database_schema()

        available_accounts = get_available_accounts()
        if not available_accounts:
            logging.error("No client_secret_*.json files found. Please ensure you have at least one client secret file.")
            return

        if args.command == 'get':
            account_id = setup_accounts(args)
            if account_id is None:
                return

            if args.subscriptions:
                handle_subscriptions(args, account_id)
            elif args.watched:
                handle_watch_history(args, account_id)

        elif args.command == 'import':
            source_account_id, target_account_id = setup_accounts(args)
            if source_account_id is None or target_account_id is None:
                return

            handle_import_subscriptions(args, source_account_id, target_account_id)

    except Exception as e:
        logging.error(f"An unexpected error occurred: {str(e)}")
        logging.error(f"Error details: {traceback.format_exc()}")
    finally:
        if args.command != 'get' or not args.watched:
            log_quota_info()
        # Save quota details at the end of the script
        save_quota_details()
        logging.info("YouTube Subscription Manager finished")

def handle_watch_history(args, account_id):
    credentials_path = f'token_{args.account}.json'
    watch_history = get_watch_history(credentials_path, args.max_results)
    if watch_history:
        print_watch_history(watch_history)
    else:
        logging.warning("Failed to retrieve watch history.")

def log_quota_info():
    log_quota_information()
    
    actual_quota = get_actual_quota()
    remaining_quota = actual_quota - get_quota_usage()
    if remaining_quota <= 0:
        next_reset = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        logging.warning(f"Quota limit reached. The script will be able to process more subscriptions after the next reset.")
        logging.info(f"Next quota reset: {next_reset.strftime('%Y-%m-%d %H:%M:%S')} (in {(next_reset - datetime.now()).total_seconds() / 3600:.2f} hours)")
    else:
        estimated_remaining = estimate_processable_subscriptions()
        logging.info(f"Estimated number of additional subscriptions that can be processed: {estimated_remaining}")
        
        # Add warning if remaining quota is less than 10% of the daily quota
        if remaining_quota < (actual_quota * 0.1):
            logging.warning(f"Remaining quota is low: {remaining_quota} units (less than 10% of daily quota)")
            logging.warning("Consider pausing operations to avoid hitting the quota limit")

if __name__ == '__main__':
    main()
