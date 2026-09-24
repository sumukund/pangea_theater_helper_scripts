import requests
from simple_salesforce import Salesforce, SalesforceAuthenticationFailed

# --- CONFIGURATION ---
SF_USERNAME = "your_salesforce_username@domain.com"
SF_PASSWORD = "your_salesforce_password"
SF_SECURITY_TOKEN = "your_salesforce_security_token"
SF_DOMAIN = "login"

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

# --- 2. SIMULATE OR LOAD ZEFFY WEBHOOK PAYLOAD ---
# If you are reading from a saved json file:
# import json
# with open("zeffy_webhook.json") as f:
#     payload = json.load(f)

# Using your exact sample payload directly for demonstration:
payload = {
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "type": "payment.completed",
  "data": {
    "amount": 5000,
    "currency": "cad",
    "description": "Annual Gala 2025",
    "buyer": {
      "email": "jane@example.com",
      "first_name": "Jane",
      "last_name": "Doe"
    }
  }
}

# --- 3. PARSE AND PUSH TO SALESFORCE ---
if payload.get("type") == "payment.completed":
    payment = payload.get("data", {})
    buyer = payment.get("buyer", {})
    
    email = buyer.get("email")
    first_name = buyer.get("first_name", "")
    last_name = buyer.get("last_name", "Supporter")  # Salesforce requires a LastName
    amount = payment.get("amount", 0) / 100.0        # Convert cents (5000) to dollars ($50.00)
    description = payment.get("description", "Zeffy Donation")

    if not email:
        print("Skipping record: No email address found.")
        exit(0)

    print(f"Processing: {first_name} {last_name} ({email}) - ${amount} for '{description}'")

    try:
        # Upsert Contact based on Email to prevent duplicates
        contact_result = sf.Contact.upsert(
            'Email', 
            email, 
            {
                'FirstName': first_name,
                'LastName': last_name
            }
        )
        print(f"Successfully synced contact {email} to Salesforce.")
        
        # Optional: Fetch the Contact ID to create a linked Donation/Opportunity record
        # (Useful if you want to track the $50 amount tied to "Annual Gala 2025")
        contact_record = sf.Contact.get_by_id(contact_result.get('id')) if contact_result else None
        
    except Exception as e:
        print(f"Error syncing {email} to Salesforce: {e}")

print("Sync execution completed.")
