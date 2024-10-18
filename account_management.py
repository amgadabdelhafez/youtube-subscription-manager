import os
import re
from utils import log
from database import get_or_create_account

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

def setup_accounts(args):
    if args.command == 'get':
        account_id = get_or_create_account(args.account)
        if account_id is None:
            log(f"Failed to get or create account {args.account}")
            return None
        return account_id
    elif args.command == 'import':
        source_account_id = get_or_create_account(args.from_account)
        target_account_id = get_or_create_account(args.to_account)
        if source_account_id is None or target_account_id is None:
            log(f"Failed to get or create accounts")
            return None, None
        return source_account_id, target_account_id
