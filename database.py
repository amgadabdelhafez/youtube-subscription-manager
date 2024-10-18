import sqlite3
import os
from utils import log

def get_db_connection(db_name="subscriptions.db"):
    db_path = os.path.abspath(db_name)
    return sqlite3.connect(db_path)

def update_database_schema(db_name="subscriptions.db"):
    conn = get_db_connection(db_name)
    cursor = conn.cursor()
    try:
        # Create accounts table
        cursor.execute('''CREATE TABLE IF NOT EXISTS accounts
                          (id INTEGER PRIMARY KEY AUTOINCREMENT,
                           name TEXT UNIQUE NOT NULL)''')
        
        # Check if the subscriptions table exists and update its schema
        cursor.execute('''CREATE TABLE IF NOT EXISTS subscriptions 
                            (channel_id TEXT PRIMARY KEY, 
                            title TEXT, 
                            description TEXT, 
                            published_at TEXT, 
                            created_at TEXT,
                            total_videos TEXT,
                            last_upload_date TEXT,
                            upload_frequency TEXT,
                            account_id_1 INTEGER,
                            account_id_2 INTEGER,
                            FOREIGN KEY (account_id_1) REFERENCES accounts(id),
                            FOREIGN KEY (account_id_2) REFERENCES accounts(id))''')

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

        # Create problematic_subscriptions table
        cursor.execute('''CREATE TABLE IF NOT EXISTS problematic_subscriptions
                          (id INTEGER PRIMARY KEY AUTOINCREMENT,
                           channel_id TEXT,
                           account_id INTEGER,
                           reason TEXT,
                           flagged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                           FOREIGN KEY (account_id) REFERENCES accounts(id),
                           UNIQUE(channel_id, account_id))''')

        conn.commit()
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
    existing_subs = set()
    subs = []
    try:
        cursor.execute("SELECT channel_id, title FROM subscriptions WHERE account_id_1 = ? OR account_id_2 = ?", (account_id, account_id))
        for row in cursor.fetchall():
            existing_subs.add(row[0])
            subs.append({'channel_id': row[0], 'title': row[1]})
    except sqlite3.Error as e:
        log(f"An error occurred while fetching existing subscriptions: {e}")
    finally:
        conn.close()
    return existing_subs, subs

def store_subscriptions_in_db(subscriptions, account_id, source="api", db_name="subscriptions.db"):
    log(f"Storing {len(subscriptions)} subscriptions for account ID {account_id}")
    conn = get_db_connection(db_name)
    cursor = conn.cursor()
    updated_channels = []
    new_channels = []
    
    try:
        conn.execute("BEGIN")
        
        for sub in subscriptions:
            try:
                # Check if the subscription already exists
                cursor.execute("SELECT account_id_1, account_id_2 FROM subscriptions WHERE channel_id = ?", (sub['channel_id'],))
                existing = cursor.fetchone()
                
                if existing:
                    account_id_1, account_id_2 = existing
                    if account_id not in (account_id_1, account_id_2):
                        # Add the new account_id to the correct column
                        if account_id_1 is None:
                            account_id_1 = account_id
                        elif account_id_2 is None:
                            account_id_2 = account_id
                        # If both slots are filled, we don't change anything
                    
                    # Ensure account_id is in the correct column
                    if account_id_1 is not None and account_id_2 is not None and account_id_1 > account_id_2:
                        account_id_1, account_id_2 = account_id_2, account_id_1
                    
                    cursor.execute('''UPDATE subscriptions 
                                      SET title = ?, description = ?, published_at = ?, 
                                          created_at = ?, total_videos = ?, last_upload_date = ?, 
                                          upload_frequency = ?, account_id_1 = ?, account_id_2 = ?
                                      WHERE channel_id = ?''',
                                   (sub['title'], sub.get('description', 'N/A'),
                                    sub.get('published_at', 'N/A'), sub.get('created_at', 'N/A'),
                                    sub.get('total_videos', 'N/A'), sub.get('last_upload_date', 'N/A'),
                                    sub.get('upload_frequency', 'N/A'), account_id_1, account_id_2,
                                    sub['channel_id']))
                    updated_channels.append(sub['channel_id'])
                    log(f"Updated existing channel: {sub['title']} ({sub['channel_id']})")
                else:
                    # New subscription
                    cursor.execute('''INSERT INTO subscriptions 
                                      (channel_id, title, description, published_at, created_at, 
                                       total_videos, last_upload_date, upload_frequency, account_id_1) 
                                      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                                   (sub['channel_id'], sub['title'], sub.get('description', 'N/A'),
                                    sub.get('published_at', 'N/A'), sub.get('created_at', 'N/A'),
                                    sub.get('total_videos', 'N/A'), sub.get('last_upload_date', 'N/A'),
                                    sub.get('upload_frequency', 'N/A'), account_id))
                    new_channels.append(sub['channel_id'])
                    log(f"Added new channel: {sub['title']} ({sub['channel_id']})")
                
            except sqlite3.Error as e:
                log(f"Error inserting subscription {sub['channel_id']}: {e}")
        
        conn.commit()
        log(f"Database transaction committed. Updated {len(updated_channels)} channels, added {len(new_channels)} new channels.")
    except sqlite3.Error as e:
        log(f"An error occurred while storing subscriptions: {e}")
        conn.rollback()
        log("Changes rolled back due to error.")
    finally:
        conn.close()
    
    return updated_channels + new_channels

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

def flag_problematic_subscription(account_id, channel_id, reason, db_name="subscriptions.db"):
    log(f"Flagging problematic subscription: Account ID {account_id}, Channel ID {channel_id}, Reason: {reason}")
    conn = get_db_connection(db_name)
    cursor = conn.cursor()
    
    try:
        cursor.execute('''INSERT OR REPLACE INTO problematic_subscriptions 
                          (channel_id, account_id, reason) 
                          VALUES (?, ?, ?)''', 
                       (channel_id, account_id, reason))
        
        conn.commit()
        log(f"Problematic subscription flagged: Channel ID {channel_id}")
    except sqlite3.Error as e:
        log(f"An error occurred while flagging problematic subscription: {e}")
    finally:
        conn.close()
