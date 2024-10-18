import argparse

def parse_arguments():
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

    return parser.parse_args()
