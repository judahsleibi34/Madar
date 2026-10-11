"""Run the existing notification consumer against isolated local Supabase only."""
import argparse
import os
from run_local import configure_local_environment, LOCAL_SCHEMA_CONTRACTS


def configure_worker(schema_contract):
    configure_local_environment(local_database=True, schema_contract=schema_contract)
    os.environ['NOTIFICATION_WORKER_ENABLED'] = 'true'
    # External transports need separate explicit configuration. Development
    # starts with the existing internal channel; no SMTP/push side effects.
    os.environ['EMAIL_CHANNEL_ENABLED'] = 'false'
    os.environ['WEB_PUSH_ENABLED'] = 'false'
    os.environ['NOTIFICATION_WORKER_HEALTH_HOST'] = '127.0.0.1'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--local-schema-contract', choices=LOCAL_SCHEMA_CONTRACTS, default='release.json')
    args = parser.parse_args()
    configure_worker(args.local_schema_contract)
    from workers.notification_worker import main
    raise SystemExit(main())
