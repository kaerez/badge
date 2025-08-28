GitHub Actions Open Badge Issuer (Advanced)
This repository contains a complete, automated system for issuing W3C-compliant Open Badges. It uses a central badges.yml file as the single source of truth for badge definitions, issuer profiles, and dynamic user inputs.
Key Features
 * Single Source of Truth: Define all badges, inputs, and issuer profiles in badges.yml.
 * Reusable Issuer Profiles: Define issuers once in a dedicated issuers section and reference them by a simple ID in your badges.
 * Dynamic Workflow UI: The system automatically builds the badge generation UI based on the inputs your badges actually use.
 * Per-Badge Input Requirements: Define and enforce which inputs are mandatory for each specific badge.
 * Secure & Granular Secrets: Each private key is stored in its own dedicated GitHub Secret.
 * Automated System Maintenance: A "meta" workflow automatically syncs the UI and generates public issuer files, keeping the system aligned with your badges.yml configuration.
How It Works
The system is driven by a "configuration-as-code" principle. The update-workflow.yml acts as a system builder. When you modify badges.yml, it reads your configuration and:
 * Rewrites the UI of the generate-badge.yml workflow to match the inputs you've defined.
 * Generates public issuer.json files for each profile defined in the issuers section.
!(https://i.imgur.com/your-advanced-workflow-diagram.png)
Setup Instructions
1. Key Pair Generation and Format
You need an RSA key pair for each distinct issuer profile.
1. Generate Keys:
openssl genrsa -out my-issuer-private.pem 2048
openssl rsa -in my-issuer-private.pem -pubout -out my-issuer-public.pem

2. Public Key: Place the public key file (e.g., my-issuer-public.pem) in the /public directory.
3. Private Key: The full content of the private key .pem file will be stored as a GitHub Secret.
2. Configure GitHub Secrets
Go to Settings > Secrets and variables > Actions. Create the following secrets:
 * RECIPIENT_SALT: A single, long, random string. Do not change this after you start issuing badges.
 * Private Key Secrets: For each private key, create a separate secret. The name of the secret must exactly match the name used in the private_key_secret_name field for your issuers in badges.yml.
3. Set up GitHub Pages
 * Enable Pages: Go to Settings > Pages. Deploy from the main branch and /(root) folder.
 * Update badges.yml: Set the repository_url to your GitHub Pages URL.
Usage
Defining Issuers and Badges
 * Define Issuers: In badges.yml, create profiles in the issuers section. Each issuer needs a unique ID (e.g., acme_community).
 * Define Global Inputs: Populate the global_inputs section with all possible input fields.
 * Define a Badge:
   * Add a new entry under badges.
   * Set the issuer_id to one of the keys defined in your issuers section.
   * In its inputs block, reference keys from global_inputs and set them to true to make them required.
 * Commit and Push: The update-workflow will automatically run, reconfiguring the entire system.
