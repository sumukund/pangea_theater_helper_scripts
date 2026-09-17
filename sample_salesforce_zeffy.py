# curl -X GET "https://zeffy.com" \
#      -H "Authorization: Bearer YOUR_ZEFFY_API_KEY" \
#      -H "Accept: application/json" \
#      -o zeffy_donations.json

# npm install -g @salesforce/cli
# # This opens a browser window to securely log into Salesforce
# sf org login web --alias my-salesforce-org --set-default

# sf data upsert bulk \
#    --sobject Contact \
#    --external-id Email \
#    --file upload.csv \
#    --target-org my-salesforce-org


## API references

## Zeffy API
# https://support.zeffy.com/get-started-with-the-zeffy-api-yourg#who-can-access-the-api

## Salesforce REST API 
# https://developer.salesforce.com/docs/platform/api-rest/guide/intro-rest.html



import requests
from simple_salesforce import Salesforce, SalesforceAuthenticationFailed

# --- CONFIGURATION ---
ZEFFY_API_KEY = "YOUR_ZEFFY_API_KEY"
ZEFFY_URL = "https://zeffy.com"

SF_USERNAME = "your_salesforce_username@domain.com"
SF_PASSWORD = "your_salesforce_password"
SF_SECURITY_TOKEN = "your_salesforce_security_token"
SF_DOMAIN = "login"  # Change to 'test' if using a Salesforce Sandbox org

# --- 1. CONNECT TO SALESFORCE ---
print("Connecting to Salesforce...")
try:
    sf = Salesforce(
        username=SF_USERNAME, 
        password=SF_PASSWORD, 
        security_token=SF_SECURITY_TOKEN, 
        domain=SF_DOMAIN
    )
    print("Successfully connected to Salesforce.")
except SalesforceAuthenticationFailed as e:
    print(f"Salesforce login failed: {e}")
    exit(1)

# --- 2. FETCH DONATIONS FROM ZEFFY ---
print("Fetching donation list from Zeffy...")
headers = {
    "Authorization": f"Bearer {ZEFFY_API_KEY}",
    "Accept": "application/json"
}

response = requests.get(ZEFFY_URL, headers=headers)

if response.status_code != 200:
    print(f"Failed to fetch from Zeffy: {response.status_code} - {response.text}")
    exit(1)

data = response.json()
# Zeffy lists data inside a 'data' array or directly as a list depending on cursor setup
payments = data.get("data", data) 

print(f"Found {len(payments)} records to process.")

# --- 3. PASS DIRECTLY TO SALESFORCE ---
for payment in payments:
    # Safely extract donor information from the Zeffy payload
    # Note: Adjust field keys based on Zeffy's exact JSON nested structure (e.g., payment['buyer'])
    buyer = payment.get("buyer", {})
    email = buyer.get("email")
    first_name = buyer.get("firstName", "")
    last_name = buyer.get("lastName", "Supporter") # Salesforce requires a LastName
    amount = payment.get("amount", 0) / 100.0 # Convert cents to dollars if applicable
    
    if not email:
        print("Skipping record: No email address found.")
        continue

    print(f"Processing: {first_name} {last_name} ({email}) - ${amount}")

    # Upsert Contact in Salesforce based on Email to prevent duplicates
    try:
        sf.Contact.upsert(
            'Email', # External ID field in Salesforce used to match duplicates
            email, 
            {
                'FirstName': first_name,
                'LastName': last_name,
                # If you have a custom currency field on the Contact layout for lifetime giving:
                # 'Total_Donations__c': amount 
            }
        )
        print(f"Successfully synced {email} to Salesforce.")
        
        # OPTIONAL: If you want to log individual donations as Opportunities linked to the Contact,
        # you would query the Contact ID and insert an Opportunity record here.
        
    except Exception as e:
        print(f"Error syncing {email} to Salesforce: {e}")

print("Sync execution completed.")

