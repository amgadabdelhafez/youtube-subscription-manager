import argparse
from datetime import datetime, timedelta
import traceback
import os
import re
from auth import authenticate_youtube
from database import update_database_schema, get_existing_subscriptions, store_subscriptions_in_db, store_watch_history_in_db, get_or_create_account
from youtube_api import list_subscriptions, import_subscriptions
from utils import log, check_quota_status, get_quota_usage, estimate_processable_subscriptions, load_progress, QUOTA_LIMIT, parse_subscriptions_csv
from watch_history import process_watch_history

def get_available_accounts():
    accounts = []
    for file in os.listdir('.'):
        if file.startswith('client_secret_') and file.endswith('.json'):
            account_name = re.search(r'client_secret_(.+)\.json', file)
            if account_name:
                accounts.append(account_name.group(1))
    return accounts

def prompt_for_account(available_accounts):
    print("Available accounts:")
    for i, account in enumerate(available_accounts, 1):
        print(f"{i}. {account}")
    
    while True:
        try:
            choice = int(input("Choose an account number: "))
            if 1 <= choice <= len(available_accounts):
                return available_accounts[choice - 1]
            else:
                print("Invalid choice. Please try again.")
        except ValueError:
            print("Invalid input. Please enter a number.")

def main():
    parser = argparse.ArgumentParser(description="YouTube Subscription Manager")
    subparsers = parser.add_subparsers(dest='command', required=True)

    # Get command
    get_parser = subparsers.add_parser('get', help='Get subscriptions or watch history')
    get_parser.add_argument('--subscriptions', action='store_true', help='Get subscriptions')
    get_parser.add_argument('--watched', action='store_true', help='Get watch history')
    get_parser.add_argument('--account', required=True, help='Account ID')
    get_parser.add_argument('--format', choices=['api', 'csv', 'html', 'json'], required=True, help='Output format')
    get_parser.add_argument('--max-ops', type=int, help='Maximum number of operations')

    # Import command
    import_parser = subparsers.add_parser('import', help='Import subscriptions')
    import_parser.add_argument('--subscriptions', action='store_true', required=True, help='Import subscriptions')
    import_parser.add_argument('--from-account', required=True, help='Source account ID')
    import_parser.add_argument('--to-account', required=True, help='Target account ID')
    import_parser.add_argument('--max-ops', type=int, help='Maximum number of operations')

    args = parser.parse_args()

    try:
        # Ensure the database schema is up to date before any operations
        update_database_schema()

        # Get available accounts
        available_accounts = get_available_accounts()

        if not available_accounts:
            log("No client_secret_*.json files found. Please ensure you have at least one client secret file.")
            return

        if args.command == 'get':
            account_id = get_or_create_account(args.account)
            if account_id is None:
                log(f"Failed to get or create account {args.account}")
                return

            if args.subscriptions:
                if args.format == 'csv':
                    # Construct the CSV file path using the account name
                    csv_file = f"watch-history/{args.account}/Takeout/YouTube and YouTube Music/subscriptions/subscriptions.csv"
                    if not os.path.exists(csv_file):
                        log(f"Subscriptions CSV file not found: {csv_file}")
                        return
                    # Import subscriptions from CSV file
                    subscriptions = parse_subscriptions_csv(csv_file)
                    updated_channels = store_subscriptions_in_db(subscriptions, account_id, 'csv')
                    log(f"Imported {len(subscriptions)} subscriptions from CSV file.")
                    log(f"Updated or new channels: {len(updated_channels)}")
                elif args.format == 'api':
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

                    youtube_source = authenticate_youtube(args.account)
                    existing_subs = get_existing_subscriptions(account_id)
                    last_processed = load_progress()
                    
                    if last_processed:
                        log(f"Resuming from channel ID: {last_processed}")
                    
                    source_subscriptions = list_subscriptions(youtube_source, existing_subs, account_id, args.max_ops)
                    
                    if not source_subscriptions:
                        log("No subscriptions found or processed in the source account. This could be due to quota limitations.")
                        return
                    
                    updated_channels = store_subscriptions_in_db(source_subscriptions, account_id)
                    
                    log("\n--- Summary ---")
                    log(f"Total subscriptions processed: {len(source_subscriptions)}")
                    log(f"Updated or new channels: {len(updated_channels)}")
                else:
                    log(f"Invalid format '{args.format}' for subscriptions. Use 'api' or 'csv'.")
                    return

            elif args.watched:
                if args.format not in ['html', 'json']:
                    log(f"Invalid format '{args.format}' for watch history. Use 'html' or 'json'.")
                    return

                # Construct the watch history file path using the account name
                history_file = f"watch-history/{args.account}/Takeout/YouTube and YouTube Music/history/watch-history.{args.format}"
                if not os.path.exists(history_file):
                    log(f"Watch history file not found: {history_file}")
                    return

                total_processed = process_watch_history(history_file, account_id, args.format, args.max_ops)
                log(f"Processed {total_processed} watch history items for account {args.account}.")

        elif args.command == 'import':
            source_account_id = get_or_create_account(args.from_account)
            target_account_id = get_or_create_account(args.to_account)
            if source_account_id is None or target_account_id is None:
                log(f"Failed to get or create accounts")
                return

            # Construct the CSV file path using the from_account name
            csv_file = f"watch-history/{args.from_account}/Takeout/YouTube and YouTube Music/subscriptions/subscriptions.csv"
            if os.path.exists(csv_file):
                # Import subscriptions from CSV file
                subscriptions = parse_subscriptions_csv(csv_file)
                updated_channels = store_subscriptions_in_db(subscriptions, target_account_id)
                log(f"Imported {len(subscriptions)} subscriptions from CSV file to account {args.to_account}.")
                log(f"Updated or new channels: {len(updated_channels)}")
            else:
                youtube_source = authenticate_youtube(args.from_account)
                youtube_target = authenticate_youtube(args.to_account)
                import_subscriptions(youtube_source, youtube_target, source_account_id, target_account_id, args.max_ops)

    except Exception as e:
        log(f"An unexpected error occurred: {str(e)}")
        log(f"Error details: {traceback.format_exc()}")
    finally:
        if args.command != 'get' or not args.watched:
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
