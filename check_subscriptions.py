from database import get_existing_subscriptions

def check_subscriptions(account_id):
    existing_subs, subs = get_existing_subscriptions(account_id)
    print(f"Account {account_id} has {len(subs)} subscriptions.")

if __name__ == "__main__":
    check_subscriptions("amgadabdelhafez")
    check_subscriptions("amgadpasha")
