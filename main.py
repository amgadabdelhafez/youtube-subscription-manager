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

def main():
    args = parse_arguments()

    try:
        # Load quota details at the start of the script
        load_quota_details()

        update_database_schema()

        available_accounts = get_available_accounts()
        if not available_accounts:
            log("No client_secret_*.json files found. Please ensure you have at least one client secret file.")
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
        log(f"An unexpected error occurred: {str(e)}")
        log(f"Error details: {traceback.format_exc()}")
    finally:
        if args.command != 'get' or not args.watched:
            log_quota_info()
        # Save quota details at the end of the script
        save_quota_details()

def handle_watch_history(args, account_id):
    credentials_path = f'token_{args.account}.json'
    watch_history = get_watch_history(credentials_path, args.max_results)
    if watch_history:
        print_watch_history(watch_history)
    else:
        log("Failed to retrieve watch history.")

def log_quota_info():
    log_quota_information()
    
    remaining_quota = get_actual_quota() - get_quota_usage()
    if remaining_quota <= 0:
        next_reset = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        log(f"Quota limit reached. The script will be able to process more subscriptions after the next reset.")
        log(f"Next quota reset: {next_reset.strftime('%Y-%m-%d %H:%M:%S')} (in {(next_reset - datetime.now()).total_seconds() / 3600:.2f} hours)")
    else:
        estimated_remaining = estimate_processable_subscriptions()
        log(f"Estimated number of additional subscriptions that can be processed: {estimated_remaining}")

if __name__ == '__main__':
    main()
