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
from datetime import datetime, timezone
from urllib.parse import urlparse
import jwt
import png

def get_utc_now_iso():
    """Returns the current UTC time in the required ISO 8601 format."""
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

def get_private_key(secret_name):
    """Retrieves a specific private key directly from an environment variable."""
    key = os.environ.get(secret_name)
    if not key:
        print(f"Error: Secret '{secret_name}' not found in environment.")
        sys.exit(1)
    return key

def bake_jws_into_png(image_path, jws_string, output_path):
    """
    Bakes a JWS string into a PNG image file by adding an iTXt chunk.
    """
    try:
        # The reader is used as an iterator and does not need to be manually closed.
        reader = png.Reader(filename=image_path)
        chunks = list(reader.chunks())

        # Keyword must be 'openbadgecredential'.
        # The spec recommends no compression (flag=0, method=0), an empty language tag, and an empty translated keyword.
        keyword = b'openbadgecredential'
        null_separator = b'\x00'
        compression_flag = b'\x00'
        compression_method = b'\x00'
        language_tag = b''
        translated_keyword = b''
        text = jws_string.encode('utf-8')

        itxt_chunk_data = (
            keyword + null_separator +
            compression_flag + compression_method +
            language_tag + null_separator +
            translated_keyword + null_separator +
            text
        )
        # The pypng library expects a tuple of (chunk_type_bytes, chunk_data_bytes)
        chunk_to_add = (b'iTXt', itxt_chunk_data)

        # Insert the chunk after the IHDR chunk.
        chunks.insert(1, chunk_to_add)

        with open(output_path, 'wb') as f:
            png.write_chunks(f, chunks)
        print("Baking successful.")
    except Exception as e:
        print(f"Error baking JWS into PNG: {e}")
        sys.exit(1)

def generate_badge(args):
    print(f"--- Starting badge generation for ID: {args.badge_id} ---")
    with open('badges.yml', 'r') as f:
        config = yaml.safe_load(f)

    badge_config = config['badges'].get(args.badge_id)
    if not badge_config:
        print(f"Error: Badge ID '{args.badge_id}' not found in badges.yml.")
        sys.exit(1)

    issuer_id = badge_config['issuer_id']
    issuer_config = config['issuers'][issuer_id]
    private_key = get_private_key(issuer_config['private_key_secret_name'])
    recipient_salt = os.environ.get('RECIPIENT_SALT')
    if not recipient_salt:
        print("Error: RECIPIENT_SALT not found in secrets.")
        sys.exit(1)
    repo_url = config['repository_url']

    # 1. Create Issuer Profile
    issuer_profile = json.loads(json.dumps(issuer_config))
    issuer_filename = f"{issuer_id}-issuer.json"
    issuer_profile['id'] = f"{repo_url}/public/{issuer_filename}"
    for key, value in issuer_profile.items():
        if isinstance(value, str):
            issuer_profile[key] = value.format(repository_url=repo_url)
    issuer_profile.pop('private_key_secret_name', None)
    issuer_profile['type'] = 'Profile'

    # 2. Create Achievement
    achievement = {
        "id": f"{repo_url}/public/badges/{args.badge_id}.json",
        "type": "Achievement",
        "name": badge_config['name'],
        "description": badge_config['description'],
        "criteria": { "narrative": badge_config['criteria'] },
        "image": {
            "id": badge_config['image'].format(repository_url=repo_url),
            "type": "Image"
        }
    }

    # 3. Create Recipient Identifier
    identity_hash = hashlib.sha256(f'{args.recipient_email}{recipient_salt}'.encode('utf-8')).hexdigest()
    # Per OB 3.0, recipient identifier should be a URI. Using a URN with the hash.
    recipient_id = f"urn:sha256:{identity_hash}"

    # 4. Construct the Verifiable Credential
    credential_id = f"urn:uuid:{uuid.uuid4()}"
    vc = {
        "@context": [
            "https://www.w3.org/ns/credentials/v2",
            "https://purl.imsglobal.org/spec/ob/v3p0/context.json"
        ],
        "id": credential_id,
        "type": ["VerifiableCredential", "OpenBadgeCredential"],
        "issuer": issuer_profile,
        "validFrom": get_utc_now_iso(),
        "credentialSubject": {
            "id": recipient_id,
            "type": "AchievementSubject",
            "achievement": achievement
        }
    }
    
    # Handle optional inputs
    if getattr(args, 'expires', None):
        vc['validUntil'] = args.expires
    if getattr(args, 'startDate', None):
        vc['credentialSubject']['activityStartDate'] = args.startDate

    # 5. Create JWS
    jwt_payload = vc.copy()
    # Add required claims for VC-JWT profile
    jwt_payload.update({
        'iss': vc['issuer']['id'],
        'sub': vc['credentialSubject']['id'],
        'jti': vc['id'],
        'nbf': int(datetime.strptime(vc['validFrom'], '%Y-%m-%dT%H:%M:%SZ').timestamp())
    })
    if 'validUntil' in vc:
        jwt_payload['exp'] = int(datetime.strptime(vc['validUntil'], '%Y-%m-%dT%H:%M:%SZ').timestamp())
    
    headers = {
        "alg": "RS256",
        "typ": "vc+ld+jwt" # As per VC-JWT spec
    }
    encoded_jws = jwt.encode(jwt_payload, private_key, algorithm="RS256", headers=headers)

    # 6. Bake into PNG
    output_path = os.path.join(args.output_dir, f"{args.badge_id}-{uuid.uuid4()}.png")
    print(f"Baking badge to: {output_path}")

    image_url = achievement['image']['id']
    try:
        response = requests.get(image_url, stream=True)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching badge image from {image_url}: {e}")
        sys.exit(1)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as temp_image:
        for chunk in response.iter_content(chunk_size=8192):
            temp_image.write(chunk)
        temp_image_path = temp_image.name

    bake_jws_into_png(temp_image_path, encoded_jws, output_path)

    os.remove(temp_image_path)
    print("--- Badge generated successfully! ---")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate an Open Badge 3.0.", add_help=True)
    # Known arguments
    parser.add_argument('--badge_id', type=str, required=True, help="The ID of the badge to generate.")
    parser.add_argument('--recipient_email', type=str, required=True, help="The recipient's email address.")
    parser.add_argument('--output_dir', type=str, default='.', help="The directory to save the output badge.")

    # Dynamically add other arguments based on what's passed
    known_args, unknown_args_list = parser.parse_known_args()
    for arg in unknown_args_list:
        if arg.startswith(('--')):
            # We don't know the type, so we'll just treat it as a string
            parser.add_argument(arg.split('=')[0], type=str)

    args = parser.parse_args()
    generate_badge(args)
