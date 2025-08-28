# update_workflow.py
import yaml
import json
import os
from urllib.parse import urlparse

BADGE_CONFIG_PATH = 'badges.yml'
WORKFLOW_PATH = '.github/workflows/generate-badge.yml'
ISSUER_OUTPUT_DIR = 'public'

def update_workflow_file(config):
    """Dynamically builds and updates the generate-badge.yml workflow."""
    print("\n--- Updating Generation Workflow ---")
    
    badge_ids = list(config.get('badges', {}).keys())
    global_inputs = config.get('global_inputs', {})
    
    ui_inputs = set()
    for badge_data in config.get('badges', {}).values():
        for input_key, input_config in badge_data.get('inputs', {}).items():
            if not (isinstance(input_config, dict) and input_config.get('input') is False):
                ui_inputs.add(input_key)
    
    if any(badge.get('expires') for badge in config.get('badges', {}).values()):
        ui_inputs.add('expires')

    print(f"All unique UI inputs used across badges: {sorted(list(ui_inputs))}")

    new_workflow_inputs = {
        'badge_id': {'description': 'Select the badge', 'required': True, 'type': 'choice', 'options': sorted(badge_ids)},
        'recipient_email': {'description': "Recipient's Email", 'required': True, 'type': 'string'}
    }
    
    for input_key in sorted(list(ui_inputs)):
        input_config = global_inputs.get(input_key, {})
        if input_key == 'expires':
            input_config = {'description': 'Badge expiration - YYYY-MM-DDTHH:MM:SSZ format (optional)'}

        new_workflow_inputs[input_key] = {
            'description': input_config.get('description', f'Value for {input_key}'),
            'required': False,
            'type': 'string',
            'default': input_config.get('default', '')
        }

    try:
        with open(WORKFLOW_PATH, 'r') as f:
            workflow_data = yaml.safe_load(f)
            if not isinstance(workflow_data, dict):
                workflow_data = {} # Treat non-dict files as empty
    except FileNotFoundError:
        workflow_data = {} # Treat missing file as empty

    # **FIX**: Safely access nested keys using .get() to prevent KeyError
    current_inputs = workflow_data.get('on', {}).get('workflow_dispatch', {}).get('inputs')
        
    if current_inputs == new_workflow_inputs:
        print("Workflow UI is already up-to-date.")
        return

    print("Workflow UI is outdated. Rebuilding...")
    # Ensure the nested dictionary structure exists before assigning to it
    workflow_data.setdefault('on', {}).setdefault('workflow_dispatch', {})['inputs'] = new_workflow_inputs
    
    with open(WORKFLOW_PATH, 'w') as f:
        yaml.dump(workflow_data, f, sort_keys=False, width=120)
    print(f"Successfully updated {WORKFLOW_PATH}.")


def generate_issuer_files(config):
    """Generates public issuer JSON files from the issuers block."""
    print("\n--- Generating Issuer Files ---")
    os.makedirs(ISSUER_OUTPUT_DIR, exist_ok=True)
    repo_url = config['repository_url']
    
    for issuer_id, issuer_data in config.get('issuers', {}).items():
        filename = f"{issuer_id}-issuer.json"
        output_path = os.path.join(ISSUER_OUTPUT_DIR, filename)
        issuer_profile = json.loads(json.dumps(issuer_data))
        issuer_profile['id'] = f"{repo_url}/{ISSUER_OUTPUT_DIR}/{filename}"
        
        for key, value in issuer_profile.items():
            if isinstance(value, str):
                issuer_profile[key] = value.format(repository_url=repo_url)
        
        issuer_profile.update({'@context': "https://w3id.org/openbadges/v2", 'type': "Issuer"})
        issuer_profile.pop('private_key_secret_name', None)

        with open(output_path, 'w') as f:
            json.dump(issuer_profile, f, indent=2)
        print(f"Generated/Updated issuer file: {output_path}")

if __name__ == "__main__":
    print("--- Starting update process ---")
    with open(BADGE_CONFIG_PATH, 'r') as f:
        config = yaml.safe_load(f)
    
    update_workflow_file(config)
    generate_issuer_files(config)
    print("\n--- Update process finished ---")
