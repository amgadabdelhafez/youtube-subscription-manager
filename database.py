import sqlite3
import os
from utils import log

def get_db_connection(db_name="subscriptions.db"):
    db_path = os.path.abspath(db_name)
    log(f"Connecting to database: {db_path}")
    return sqlite3.connect(db_path)

def update_database_schema(db_name="subscriptions.db"):
    conn = get_db_connection(db_name)
    cursor = conn.cursor()
    try:
        # Create accounts table
        cursor.execute('''CREATE TABLE IF NOT EXISTS accounts
                          (id INTEGER PRIMARY KEY AUTOINCREMENT,
                           name TEXT UNIQUE NOT NULL)''')
        
        # Check if the subscriptions table exists
        cursor.execute('''CREATE TABLE IF NOT EXISTS subscriptions 
                            (channel_id TEXT PRIMARY KEY, 
                            title TEXT, 
                            description TEXT, 
                            published_at TEXT, 
                            created_at TEXT,
                            total_videos TEXT,
                            last_upload_date TEXT,
                            upload_frequency TEXT,
                            account_id INTEGER,
                            FOREIGN KEY (account_id) REFERENCES accounts(id))''')

        
        # Check if the watch_history table exists
        cursor.execute('''CREATE TABLE IF NOT EXISTS watch_history 
                            (id INTEGER PRIMARY KEY AUTOINCREMENT,
                            title TEXT,
                            url TEXT,
                            watch_time TEXT,
                            video_id TEXT,
                            channel_id TEXT,
                            account_id INTEGER,
                            FOREIGN KEY (account_id) REFERENCES accounts(id))''')

        
        conn.commit()
        log("Database schema updated successfully.")
    except sqlite3.Error as e:
        log(f"An error occurred while updating the database schema: {e}")
    finally:
        conn.close()

def get_or_create_account(account_name, db_name="subscriptions.db"):
    conn = get_db_connection(db_name)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT OR IGNORE INTO accounts (name) VALUES (?)", (account_name,))
        cursor.execute("SELECT id FROM accounts WHERE name = ?", (account_name,))
        account_id = cursor.fetchone()[0]
        conn.commit()
        return account_id
    except sqlite3.Error as e:
        log(f"An error occurred while getting or creating account: {e}")
        return None
    finally:
        conn.close()

def get_existing_subscriptions(account_id, db_name="subscriptions.db"):
    update_database_schema(db_name)
    conn = get_db_connection(db_name)
    cursor = conn.cursor()
    existing_subs = {}
    try:
        cursor.execute("SELECT channel_id, last_upload_date FROM subscriptions WHERE account_id = ?", (account_id,))
        for row in cursor.fetchall():
            existing_subs[row[0]] = row[1]
    except sqlite3.Error as e:
        log(f"An error occurred while fetching existing subscriptions: {e}")
    finally:
        conn.close()
    return existing_subs

def store_subscriptions_in_db(subscriptions, account_id, source="api", db_name="subscriptions.db"):
    log(f"Storing {len(subscriptions)} subscriptions for account ID {account_id} from {source} in {db_name}...")
    conn = get_db_connection(db_name)
    cursor = conn.cursor()
    updated_channels = []
    
    try:
        # Debug: Log the first subscription
        if subscriptions:
            log(f"Debug: First subscription data: {subscriptions[0]}")
        else:
            log("Debug: No subscriptions to store")

        # Start a transaction
        conn.execute("BEGIN")
        
        # Insert or update the subscriptions
        for sub in subscriptions:
            try:
                cursor.execute('''INSERT OR REPLACE INTO subscriptions 
                                  (channel_id, title, description, published_at, created_at, total_videos, last_upload_date, upload_frequency, account_id) 
                                  VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
                               (sub['channel_id'], sub['title'], sub.get('description', 'N/A'), 
                                sub.get('published_at', 'N/A'), sub.get('created_at', 'N/A'), 
                                sub.get('total_videos', 'N/A'), sub.get('last_upload_date', 'N/A'),
                                sub.get('upload_frequency', 'N/A'), account_id))
                updated_channels.append(sub['channel_id'])
            except sqlite3.Error as e:
                log(f"Error inserting subscription {sub['channel_id']}: {e}")
        
        log("Debug: About to commit changes...")
        conn.commit()
        log("Debug: Changes committed.")
        
        # Verify the insertion immediately after commit
        cursor.execute("SELECT COUNT(*) FROM subscriptions WHERE account_id = ?", (account_id,))
        count = cursor.fetchone()[0]
        log(f"Debug: Immediately after commit, total subscriptions in database for account ID {account_id}: {count}")
        
        if count > 0:
            cursor.execute("SELECT * FROM subscriptions WHERE account_id = ? LIMIT 1", (account_id,))
            sample_row = cursor.fetchone()
            log(f"Debug: Sample row from database: {sample_row}")
        
        log(f"Subscriptions for account ID {account_id} stored in database.")
    except sqlite3.Error as e:
        log(f"An error occurred while storing subscriptions: {e}")
        conn.rollback()
        log("Changes rolled back due to error.")
    finally:
        conn.close()
    
    # Double-check after connection is closed and reopened
    conn = get_db_connection(db_name)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COUNT(*) FROM subscriptions WHERE account_id = ?", (account_id,))
        final_count = cursor.fetchone()[0]
        log(f"Debug: After reopening connection, total subscriptions in database for account ID {account_id}: {final_count}")
    except sqlite3.Error as e:
        log(f"An error occurred while double-checking subscriptions: {e}")
    finally:
        conn.close()
    
    return updated_channels

def store_watch_history_in_db(watch_history, account_id, db_name="subscriptions.db"):
    log(f"Storing {len(watch_history)} watch history items for account ID {account_id} in {db_name}...")
    update_database_schema(db_name)  # Ensure the schema is up to date
    conn = get_db_connection(db_name)
    cursor = conn.cursor()
    
    try:
        cursor.executemany('''INSERT OR REPLACE INTO watch_history 
                              (title, url, watch_time, video_id, channel_id, account_id) 
                              VALUES (?, ?, ?, ?, ?, ?)''', 
                           [(item['title'], item['url'], item['watch_time'], 
                             item['video_id'], item['channel_id'], account_id) for item in watch_history])
        
        conn.commit()
        log(f"Watch history for account ID {account_id} stored in database.")
    except sqlite3.Error as e:
        log(f"An error occurred while storing watch history: {e}")
    finally:
        conn.close()

def get_last_watch_history_item(account_id, db_name="subscriptions.db"):
    log(f"Retrieving last watch history item for account ID {account_id}...")
    update_database_schema(db_name)  # Ensure the schema is up to date
    conn = get_db_connection(db_name)
    cursor = conn.cursor()
    
    try:
        cursor.execute('''SELECT id, title, url, watch_time, video_id, channel_id 
                          FROM watch_history 
                          WHERE account_id = ? 
                          ORDER BY id DESC 
                          LIMIT 1''', (account_id,))
        result = cursor.fetchone()
        
        if result:
            last_item = {
                'index': result[0] - 1,  # Subtract 1 to match the index in the HTML file
                'title': result[1],
                'url': result[2],
                'watch_time': result[3],
                'video_id': result[4],
                'channel_id': result[5]
            }
            log(f"Last watch history item retrieved: {last_item['title']}")
            return last_item
        else:
            log("No watch history items found for this account.")
            return None
    except sqlite3.Error as e:
        log(f"An error occurred while retrieving the last watch history item: {e}")
        return None
    finally:
        conn.close()
