import json
from utils import log

# Default daily quota for YouTube Data API v3
DEFAULT_DAILY_QUOTA = 10000

# Cost of different operations in quota units
QUOTA_COST = {
    'READ': 1,
    'WRITE': 50,
    'VIDEO_UPLOAD': 1600,
    'SEARCH': 100,
    'LIST_VIDEOS': 1,  # per 5 videos
}

# Global variable to track quota usage
quota_used = 0

def reset_quota():
    global quota_used
    quota_used = 0

def use_quota(operation, count=1):
    global quota_used
    cost = QUOTA_COST.get(operation.upper(), 1) * count
    if check_quota_status(cost):
        quota_used += cost
        save_quota_details()
        return True
    return False

def get_actual_quota():
    return DEFAULT_DAILY_QUOTA

def get_remaining_quota():
    return get_actual_quota() - quota_used

def check_quota_status(cost=1):
    return get_remaining_quota() >= int(cost)

def get_quota_usage():
    return quota_used

def estimate_processable_subscriptions():
    remaining_quota = get_remaining_quota()
    # Assuming each subscription requires a READ and a WRITE operation
    cost_per_subscription = QUOTA_COST['READ'] + QUOTA_COST['WRITE']
    return remaining_quota // cost_per_subscription

def log_quota_information():
    remaining_quota = get_remaining_quota()
    log(f"Quota usage: {quota_used}")
    log(f"Remaining quota: {remaining_quota}")
    log(f"Estimated processable subscriptions: {estimate_processable_subscriptions()}")

def can_perform_operation(operation, count=1):
    cost = QUOTA_COST.get(operation.upper(), 1) * count
    return check_quota_status(cost)

def save_quota_details():
    quota_details = {
        'quota_used': quota_used,
        'remaining_quota': get_remaining_quota(),
        'estimated_processable_subscriptions': estimate_processable_subscriptions()
    }
    with open('quota_details.json', 'w') as f:
        json.dump(quota_details, f)

def load_quota_details():
    global quota_used
    try:
        with open('quota_details.json', 'r') as f:
            quota_details = json.load(f)
        quota_used = quota_details['quota_used']
        log("Loaded quota details from file.")
        log_quota_information()
    except FileNotFoundError:
        log("No saved quota details found. Starting with fresh quota.")
        reset_quota()
