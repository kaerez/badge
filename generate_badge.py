# generate_badge.py
import os
import sys
import json
import yaml
import hashlib
import uuid
import argparse
from datetime import datetime, timezone
from urllib.parse import urlparse
from pybadges import badge

def get_utc_now_iso():
    """Returns the current UTC time in the required ISO 8601 format."""
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

def validate_and_process_inputs(badge_config, global_inputs_config, args):
    """
    Validates all inputs based on the badge's rules and processes them,
    handling defaults, static values, and required checks.
    Returns a dictionary of final values to be added to the assertion.
    """
    final_values = {}
    badge_inputs = badge_config.get('inputs', {})
    
    if badge_config.get('expires'):
        badge_inputs['expires'] = badge_config['expires']

    for name, config in badge_inputs.items():
        if not isinstance(config, dict):
            config = {}

        if config.get('input') is False:
            if 'default' in config:
                final_values[name] = config['default']
                print(f"Applied static value for '{name}'.")
            continue

        user_value = getattr(args, name, None)
        
        is_required = config.get('required', True)
        if is_required and not user_value:
            print(f"Error: Input '{name}' is required for this badge but was not provided.")
            sys.exit(1)

        global_def = global_inputs_config.get(name, {})
        is_date_field = global_def.get('date') or name == 'expires'

        if user_value:
            if is_date_field:
                try:
                    datetime.strptime(user_value, '%Y-%m-%dT%H:%M:%SZ')
                except ValueError:
                    print(f"Error: Date for '{name}' is not in YYYY-MM-DDTHH:MM:SSZ format.")
                    sys.exit(1)
            final_values[name] = user_value
        else:
            if config.get('default_now'):
                if not is_date_field:
                    print(f"Error: 'default_now' is only allowed for date fields ('{name}').")
                    sys.exit(1)
                final_values[name] = get_utc_now_iso()
                print(f"Applied default 'now' timestamp for '{name}'.")
            elif 'default' in config:
                final_values[name] = config['default']
                print(f"Applied default value for '{name}'.")

    print("All inputs validated and processed successfully.")
    return final_values


def get_private_key(secret_name):
    """Retrieves a specific private key directly from an environment variable."""
    key = os.environ.get(secret_name)
    if not key:
        print(f"Error: Secret '{secret_name}' not found in environment.")
        sys.exit(1)
    return key

def generate_badge(args):
    print(f"--- Starting badge generation for ID: {args.badge_id} ---")
    with open('badges.yml', 'r') as f:
        config = yaml.safe_load(f)

    badge_config = config['badges'][args.badge_id]
    global_inputs_config = config.get('global_inputs', {})
    
    processed_inputs = validate_and_process_inputs(badge_config, global_inputs_config, args)

    issuer_id = badge_config['issuer_id']
    issuer_config = config['issuers'][issuer_id]
    
    private_key = get_private_key(issuer_config['private_key_secret_name'])
    
    recipient_salt = os.environ.get('RECIPIENT_SALT')
    if not recipient_salt:
        print("Error: RECIPIENT_SALT not found in secrets.")
        sys.exit(1)

    repo_url = config['repository_url']

    full_issuer_object = json.loads(json.dumps(issuer_config))
    issuer_filename = f"{issuer_id}-issuer.json"
    full_issuer_object['id'] = f"{repo_url}/public/{issuer_filename}"
    for key, value in full_issuer_object.items():
        if isinstance(value, str):
            full_issuer_object[key] = value.format(repository_url=repo_url)
    full_issuer_object.pop('private_key_secret_name', None)

    for key, value in badge_config.items():
        if isinstance(value, str):
            badge_config[key] = value.format(repository_url=repo_url)

    identity = f"sha256${hashlib.sha256(f'{args.recipient_email}{recipient_salt}'.encode('utf-8')).hexdigest()}"

    badge_class = {
        "type": "BadgeClass", "id": f"{repo_url}/badges/{args.badge_id}",
        "name": badge_config['name'], "description": badge_config['description'],
        "image": badge_config['image'], "criteria": {"narrative": badge_config['criteria']},
        "issuer": full_issuer_object
    }
    assertion = {
        "@context": "https://w3id.org/openbadges/v2", "type": "Assertion",
        "id": f"{repo_url}/assertions/{uuid.uuid4()}.json",
        "recipient": {"type": "email", "identity": identity, "hashed": True, "salt": recipient_salt},
        "badge": badge_class,
        "verification": {"type": "SignedBadge", "creator": full_issuer_object['publicKey']},
        "issuedOn": get_utc_now_iso(),
    }
    
    assertion.update(processed_inputs)

    output_path = os.path.join(args.output_dir, f"{args.badge_id}-{uuid.uuid4()}.png")
    
    print(f"Baking badge to: {output_path}")
    # CRITICAL FIX: Explicitly set left_text to None to force the library
    # to correctly interpret the other keyword arguments for Open Badge generation.
    badge(
        left_text=None,
        assertion=assertion,
        signature_key=private_key,
        output_file=output_path
    )
    print("--- Badge generated successfully! ---")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(add_help=False)
    known_args, unknown_args = parser.parse_known_args()
    for arg in unknown_args:
        if arg.startswith(('--')):
            parser.add_argument(arg, type=str)
    args = parser.parse_args()
    generate_badge(args)
