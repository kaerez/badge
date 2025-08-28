# update_workflow.py
import yaml
import json
import os

BADGE_CONFIG_PATH = 'badges.yml'
WORKFLOW_PATH = '.github/workflows/generate-badge.yml'
ISSUER_OUTPUT_DIR = 'public'

def update_workflow_file(config):
    """Dynamically builds and updates the generate-badge.yml workflow."""
    print("\n--- Updating Generation Workflow ---")
    
    badge_ids = list(config.get('badges', {}).keys())
    global_inputs = config.get('global_inputs', {})
    used_inputs = set(key for badge in config.get('badges', {}).values() for key in badge.get('inputs', {}))
    
    print(f"All unique inputs used across badges: {sorted(list(used_inputs))}")

    new_workflow_inputs = {
        'badge_id': {'description': 'Select the badge', 'required': True, 'type': 'choice', 'options': sorted(badge_ids)},
        'recipient_email': {'description': "Recipient's Email", 'required': True, 'type': 'string'}
    }
    for key in sorted(list(used_inputs)):
        if key in global_inputs:
            new_workflow_inputs[key] = {
                'description': global_inputs[key].get('description', f'Value for {key}'),
                'required': False, 'type': 'string'
            }

    with open(WORKFLOW_PATH, 'r') as f:
        workflow_data = yaml.safe_load(f)
        
    if workflow_data['on']['workflow_dispatch']['inputs'] == new_workflow_inputs:
        print("Workflow UI is already up-to-date.")
        return

    print("Workflow UI is outdated. Rebuilding...")
    workflow_data['on']['workflow_dispatch']['inputs'] = new_workflow_inputs
    
    with open(WORKFLOW_PATH, 'w') as f:
        yaml.dump(workflow_data, f, sort_keys=False, width=120)
    print(f"Successfully updated {WORKFLOW_PATH}.")

def generate_issuer_files(config):
    """Generates public issuer JSON files from the issuers block."""
    print("\n--- Generating Issuer Files ---")
    os.makedirs(ISSUER_OUTPUT_DIR, exist_ok=True)
    repo_url = config['repository_url']
    
    for issuer_id, issuer_data in config.get('issuers', {}).items():
        # The filename is derived from the issuer ID.
        filename = f"{issuer_id}-issuer.json"
        output_path = os.path.join(ISSUER_OUTPUT_DIR, filename)
        
        # Create a deep copy to avoid modifying the original dict
        issuer_profile = json.loads(json.dumps(issuer_data))
        
        # Add the required 'id' field for the issuer profile
        issuer_profile['id'] = f"{repo_url}/{ISSUER_OUTPUT_DIR}/{filename}"
        
        # Resolve the {repository_url} placeholder for other fields like publicKey
        for key, value in issuer_profile.items():
            if isinstance(value, str):
                issuer_profile[key] = value.format(repository_url=repo_url)
        
        # Add required context and type
        issuer_profile.update({'@context': "https://w3id.org/openbadges/v2", 'type': "Issuer"})
        # Remove the secret name from the public file
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
