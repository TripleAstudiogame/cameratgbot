import os
from dotenv import load_dotenv
import db
import json

def migrate():
    load_dotenv()
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    mail_username = os.getenv("MAIL_USERNAME")
    mail_password = os.getenv("MAIL_APP_PASSWORD")

    if not bot_token or not mail_username or not mail_password:
        print("No .env data found to migrate.")
        return

    # Check if we already have it
    orgs = db.get_organizations()
    if any(o['mail_username'] == mail_username for o in orgs):
        print("Data already migrated.")
        return

    # Create first org
    data = {
        'name': 'Главный Офис (Миграция)',
        'bot_token': bot_token,
        'mail_username': mail_username,
        'mail_password': mail_password
    }
    
    new_id = db.add_organization(data)
    print(f"Migrated .env to organization ID: {new_id}")

    # Migrate subscribers if exists
    if os.path.exists('subscribers.json'):
        try:
            with open('subscribers.json', 'r') as f:
                subs = json.load(f)
                for sub in subs:
                    db.add_subscriber(new_id, sub)
            print(f"Migrated {len(subs)} subscribers.")
        except Exception as e:
            print(f"Failed to migrate subscribers: {e}")

if __name__ == "__main__":
    migrate()
