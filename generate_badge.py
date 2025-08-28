# generate_badge.py
import os
import sys
import json
import yaml
import hashlib
import uuid
import argparse
import requests
import tempfile
import png
from datetime import datetime, timezone
from jwcrypto import jwk, jws

def get_utc_now_iso():
    """Returns the current UTC time in the required ISO 8601 format."""
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

def validate_and_process_inputs(badge_config, global_inputs_config, args):
    """
    Validates all inputs based on the badge's rules and processes them,
    handling defaults, static values, and required checks.
    Returns a dictionary of final values to be added to the credential.
    """
    final_values = {}
    badge_inputs = badge_config.get('inputs', {})
    
    if badge_config.get('expires'):
        badge_inputs['expires'] = {'description': 'Badge expiration date'}

    for name, config in badge_inputs.items():
        if not isinstance(config, dict):
            config = {}

        if config.get('input') is False:
            if 'default' in config:
                final_values[name] = config['default']
            continue

        user_value = getattr(args, name, None)
        
        is_required = config.get('required', True) if name != 'expires' else False
        if is_required and not user_value:
            print(f"Error: Input '{name}' is required but was not provided.")
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
            elif 'default' in config:
                final_values[name] = config['default']

    print("All inputs validated and processed successfully.")
    return final_values

def sign_credential(payload, private_key_pem):
    """Signs a dictionary payload and returns a JWS."""
    private_key = jwk.JWK.from_pem(private_key_pem.encode('utf-8'))
    jwstoken = jws.JWS(json.dumps(payload).encode('utf-8'))
    jwstoken.add_signature(private_key, None, json.dumps({"alg": "RS256"}), protected=json.dumps({"b64": False, "crit": ["b64"]}))
    return jwstoken.serialize(compact=True)

def embed_jws_in_png(input_image_path, jws_string, output_path):
    """Embeds a JWS string into the metadata of a PNG image."""
    reader = png.Reader(filename=input_image_path)
    chunks = reader.chunks()
    new_chunk = ('iTXt', b'openbadges\x00\x00\x00\x00\x00' + jws_string.encode('utf-8'))
    chunk_list = list(chunks)
    chunk_list.insert(1, new_chunk)
    with open(output_path, 'wb') as f:
        png.write_chunks(f, chunk_list)

def generate_badge(args):
    """Generates an Open Badge 3.0 as a JWS embedded in a PNG."""
    print(f"--- Starting OBv3 badge generation for ID: {args.badge_id} ---")

    with open('badges.yml', 'r') as f:
        config = yaml.safe_load(f)

    badge_config = config['badges'][args.badge_id]
    global_inputs_config = config.get('global_inputs', {})
    issuer_id = badge_config['issuer_id']
    issuer_config = config['issuers'][issuer_id]
    repo_url = config['repository_url']

    processed_inputs = validate_and_process_inputs(badge_config, global_inputs_config, args)

    recipient_salt = os.environ.get('RECIPIENT_SALT')
    if not recipient_salt:
        print("Error: RECIPIENT_SALT not found in secrets.")
        sys.exit(1)
    hashed_email = hashlib.sha256(f'{args.recipient_email}{recipient_salt}'.encode('utf-8')).hexdigest()

    credential = {
        "@context": ["https://www.w3.org/ns/credentials/v2", "https://purl.imsglobal.org/spec/ob/v3p0/context-3.0.0.json"],
        "id": f"urn:uuid:{uuid.uuid4()}",
        "type": ["VerifiableCredential", "OpenBadgeCredential"],
        "issuer": f"{repo_url}/public/{issuer_id}-issuer.json",
        "issuanceDate": get_utc_now_iso(),
        "credentialSubject": {
            "type": "AchievementSubject",
            "achievement": {
                "id": f"{repo_url}/public/badges/{args.badge_id}.json",
                "type": "Achievement",
            },
            "source": {
                "id": f"urn:email:{hashed_email}",
                "type": "Identity",
                "hashed": True,
                "salt": recipient_salt
            }
        }
    }
    
    if 'expires' in processed_inputs:
        credential['expirationDate'] = processed_inputs.pop('expires')
    
    # Add any other processed inputs as custom fields
    if processed_inputs:
        credential['credentialSubject']['customFields'] = processed_inputs


    private_key_pem = os.environ.get(issuer_config['private_key_secret_name'])
    if not private_key_pem:
        print(f"Error: Secret '{issuer_config['private_key_secret_name']}' not found.")
        sys.exit(1)

    print("Signing the credential...")
    signed_jws = sign_credential(credential, private_key_pem)

    image_url = badge_config['image'].format(repository_url=repo_url)
    output_filename = f"{args.badge_id}-{uuid.uuid4()}.png"
    output_path = os.path.join(args.output_dir, output_filename)

    print(f"Embedding signed JWS into PNG: {output_path}")
    response = requests.get(image_url, stream=True)
    response.raise_for_status()

    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as temp_image:
        for chunk in response.iter_content(chunk_size=8192):
            temp_image.write(chunk)
        temp_image_path = temp_image.name

    embed_jws_in_png(temp_image_path, signed_jws, output_path)
    os.remove(temp_image_path)

    print("--- OBv3 badge generated successfully! ---")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(add_help=False)
    # This is the robust parser from the original file
    known_args, unknown_args = parser.parse_known_args()
    for arg in unknown_args:
        if arg.startswith(('--')):
            parser.add_argument(arg, type=str)
    args = parser.parse_args()
    generate_badge(args)
