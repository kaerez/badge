# generate_badge.py
import os
import sys
import json
import yaml
import hashlib
import uuid
import argparse
from datetime import datetime
from pybadges import badge

def validate_inputs(badge_config, args):
    required = [k for k, v in badge_config.get('inputs', {}).items() if v]
    missing = [r for r in required if not getattr(args, r, None)]
    if missing:
        print(f"Error: Badge '{args.badge_id}' requires inputs: {', '.join(missing)}")
        sys.exit(1)
    print("All required inputs are present.")

def get_private_key(secret_name):
    key = os.environ.get(secret_name)
    if not key:
        print(f"Error: Secret '{secret_name}' not found. Ensure it is created in repository settings.")
        sys.exit(1)
    return key

def generate_badge(args):
    print(f"--- Starting badge generation for ID: {args.badge_id} ---")
    with open('badges.yml', 'r') as f:
        config = yaml.safe_load(f)

    badge_config = config['badges'][args.badge_id]
    validate_inputs(badge_config, args)

    # Look up the issuer using the issuer_id
    issuer_id = badge_config['issuer_id']
    issuer_config = config['issuers'][issuer_id]
    
    private_key = get_private_key(issuer_config['private_key_secret_name'])
    recipient_salt = os.environ['RECIPIENT_SALT']
    repo_url = config['repository_url']

    # Build the full issuer object for the assertion
    full_issuer_object = json.loads(json.dumps(issuer_config))
    issuer_filename = f"{issuer_id}-issuer.json"
    full_issuer_object['id'] = f"{repo_url}/public/{issuer_filename}"
    for key, value in full_issuer_object.items():
        if isinstance(value, str):
            full_issuer_object[key] = value.format(repository_url=repo_url)
    full_issuer_object.pop('private_key_secret_name', None)

    # Resolve placeholders in the badge config as well
    for key, value in badge_config.items():
        if isinstance(value, str):
            badge_config[key] = value.format(repository_url=repo_url)

    identity = f"sha25{hashlib.sha256(f'{args.recipient_email}{recipient_salt}'.encode('utf-8')).hexdigest()}"

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
        "issuedOn": datetime.utcnow().isoformat() + "Z",
    }
    for arg_key, arg_val in vars(args).items():
        if arg_key not in ['badge_id', 'recipient_email', 'output_dir'] and arg_val:
             assertion[arg_key] = arg_val

    output_path = os.path.join(args.output_dir, f"{args.badge_id}-{uuid.uuid4()}.png")
    print(f"Baking badge to: {output_path}")
    badge(image=badge_config['image'], assertion=assertion, signature_key=private_key, output_file=output_path)
    print("--- Badge generated successfully! ---")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(add_help=False)
    known_args, unknown_args = parser.parse_known_args()
    for arg in unknown_args:
        if arg.startswith(('--')):
            parser.add_argument(arg, type=str)
    args = parser.parse_args()
    generate_badge(args)
