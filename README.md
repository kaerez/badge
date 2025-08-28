# **GitHub Actions Open Badge Issuer (Advanced)**

This repository contains a complete, automated system for issuing W3C-compliant Open Badges. It uses a central badges.yml file as the single source of truth for badge definitions, issuer profiles, and dynamic user inputs.

## **Key Features**

* **Single Source of Truth**: Define all badges, inputs, and issuer profiles in badges.yml.  
* **Reusable Issuer Profiles**: Define issuers once in a dedicated issuers section and reference them by a simple ID in your badges.  
* **Dynamic Workflow UI**: The system automatically builds the badge generation UI based on the inputs your badges actually use.  
* **Per-Badge Input Requirements**: Define and enforce which inputs are mandatory for each specific badge.  
* **Secure & Granular Secrets**: Each private key is stored in its own dedicated GitHub Secret.  
* **Automated System Maintenance**: A "meta" workflow automatically syncs the UI and generates public issuer files, keeping the system aligned with your badges.yml configuration.

## **Repository Structure**

.  
├── .github/workflows/  
│   ├── generate-badge.yml   \# The user-facing workflow to issue badges (AUTO-GENERATED)  
│   └── update-workflow.yml    \# The "meta" workflow that syncs the system  
├── public/  
│   ├── community-public-key.pem \# Your public keys for verification go here  
│   └── community-issuer.json  \# Public issuer profiles (AUTO-GENERATED)  
├── images/  
│   └── contributor-badge.png  \# Your badge images go here  
├── badges.yml                 \# The main configuration file for the entire system  
├── generate\_badge.py          \# Python script that generates the badge  
├── update\_workflow.py         \# Python script that updates the workflows and issuers  
├── requirements.txt           \# Python dependencies  
└── README.md                  \# This file

## **Setup Instructions**

Follow these steps to configure the system in your repository.

### **Step 1: Prepare Your Repository**

1. **Clone the Repository**: Start by cloning this repository to your local machine.  
2. **Create Directories**: Create the public/ and images/ directories in the root of the repository if they don't already exist.  
3. **Add Badge Images**: Place your badge images (e.g., contributor-badge.png) inside the /images directory.

### **Step 2: Generate Cryptographic Keys**

You need an RSA key pair for each distinct issuer profile you intend to use.

1. **Generate Keys**: You can use openssl locally or a tool like CyberChef.  
   * **Option A (Local Terminal)**: Run the following commands. Replace my-issuer with a descriptive name (e.g., community-team).  
     \# Generate a 2048-bit private key  
     openssl genrsa \-out my-issuer-private.pem 2048

     \# Extract the corresponding public key  
     openssl rsa \-in my-issuer-private.pem \-pubout \-out my-issuer-public.pem

   * **Option B (CyberChef)**: Use this pre-configured link to generate an RSA key pair directly in your browser.  
     * [**CyberChef: Generate RSA Key Pair**](https://www.google.com/search?q=https://gchq.github.io/CyberChef/%23recipe%3DGenerate_RSA_Key_Pair\(2048,65537,'PEM','PKCS8'\))  
     * Copy the generated "Private Key" and "Public Key" into .pem files.  
2. **Place Public Key**: Move the public key file (my-issuer-public.pem) into the /public directory of your repository.

### **Step 3: Configure GitHub Secrets**

Go to your repository's Settings \> Secrets and variables \> Actions. Create the following secrets:

1. **RECIPIENT\_SALT**:  
   * A single, long, random string used to hash recipient emails. **Do not change this after you start issuing badges.**  
   * You can generate a secure random string using this CyberChef link:  
     * [**CyberChef: Generate Random String for SALT**](https://www.google.com/search?q=https://gchq.github.io/CyberChef/%23recipe%3DGenerate_Random\(32,'A-Za-z0-9-_',''\)%26output%3DBase64)  
2. **Private Key Secrets**:  
   * For **each** private key you generated, create a **separate** repository secret.  
   * **The name of the secret must exactly match** the name you will use in the private\_key\_secret\_name field in badges.yml. For example, if you plan to use private\_key\_secret\_name: COMMUNITY\_SIGNING\_KEY, you must create a secret named COMMUNITY\_SIGNING\_KEY.  
   * **Value**: Copy the **full content** of the private key .pem file, including the \-----BEGIN... and \-----END... lines.

### **Step 4: Configure GitHub Pages & badges.yml**

1. **Enable Pages**: Go to Settings \> Pages. Under "Build and deployment", select the source as Deploy from a branch, choose your main branch, and the /(root) folder. Save your changes.  
2. **Update badges.yml**: Open the badges.yml file and set the repository\_url to your GitHub Pages URL (e.g., https://your-username.github.io/your-repo-name).  
3. **Configure Issuers & Badges**: Populate the badges.yml file with your issuer profiles, global inputs, and badge definitions. See the "Configuration Deep Dive" section below for details.  
4. **Commit and Push**: Commit all your changes (including the new public keys, images, and updated badges.yml) and push them to GitHub. This will trigger the Update Badge System workflow for the first time, which will generate your issuer files and configure the badge generation workflow.

## **Configuration Deep Dive (badges.yml)**

This file is the control panel for the entire system.

* repository\_url: The root URL for your GitHub Pages site.  
* issuers: A dictionary of all possible issuer profiles.  
  * acme\_community (key): A unique ID for the issuer.  
  * name, url, email: Standard issuer information.  
  * publicKey: The full URL to the issuer's public key you placed in the /public directory.  
  * private\_key\_secret\_name: The name of the GitHub Secret holding the corresponding private key.  
* global\_inputs: A library of all possible input fields your badges might use.  
  * evidence\_url (key): The ID of the input field.  
  * description: The text that will be shown to the user in the workflow UI.  
* badges: A dictionary of all issuable badges.  
  * contributor-2024 (key): A unique ID for the badge.  
  * name, description, image, criteria: Standard badge information.  
  * issuer\_id: The key of the issuer (from the issuers block) that will issue this badge.  
  * inputs: A dictionary where you list which global\_inputs are **required** for this specific badge by setting them to true.

## **Usage**

### **Generating a Badge**

1. Go to the **Actions** tab in your repository.  
2. Click on the **Generate Open Badge** workflow.  
3. Click the **Run workflow** dropdown.  
4. Select the desired badge and fill in the required information.  
5. Click **Run workflow**.  
6. Once complete, a downloadable artifact containing the signed badge PNG will be available on the workflow summary page.
