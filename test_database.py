import sqlite3
from database import get_db_connection, store_subscriptions_in_db, get_existing_subscriptions, update_database_schema
from utils import log

def test_database_operations():
    # Ensure the database schema is up to date
    update_database_schema()

    # Test data
    test_account_id = 999
    test_subscription = {
        'channel_id': 'test_channel_id',
        'title': 'Test Channel',
        'description': 'This is a test channel',
        'published_at': '2023-01-01T00:00:00Z',
        'created_at': '2023-01-01T00:00:00Z',
        'total_videos': '10',
        'last_upload_date': '2023-06-01T00:00:00Z',
        'upload_frequency': '0.5 videos per day'
    }

    # Step 1: Insert test subscription
    log("Step 1: Inserting test subscription")
    updated_channels = store_subscriptions_in_db([test_subscription], test_account_id)
    log(f"Inserted channels: {updated_channels}")

    # Step 2: Retrieve the inserted subscription
    log("Step 2: Retrieving inserted subscription")
    existing_subs, subs = get_existing_subscriptions(test_account_id)
    log(f"Retrieved subscriptions: {subs}")

    # Step 3: Update the subscription
    log("Step 3: Updating test subscription")
    test_subscription['title'] = 'Updated Test Channel'
    updated_channels = store_subscriptions_in_db([test_subscription], test_account_id)
    log(f"Updated channels: {updated_channels}")

    # Step 4: Retrieve the updated subscription
    log("Step 4: Retrieving updated subscription")
    existing_subs, subs = get_existing_subscriptions(test_account_id)
    log(f"Retrieved subscriptions: {subs}")

    # Cleanup: Remove test data
    log("Cleaning up test data")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM subscriptions WHERE channel_id = ?", (test_subscription['channel_id'],))
    conn.commit()
    conn.close()

if __name__ == "__main__":
    test_database_operations()
