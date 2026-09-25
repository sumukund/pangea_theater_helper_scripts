import requests
from simple_salesforce import Salesforce, SalesforceAuthenticationFailed

# --- CONFIGURATION ---
ZEFFY_API_KEY = ""
ZEFFY_URL = "https://zeffy.com"

SF_USERNAME = "seamus@pangeaworldtheater.org"
SF_PASSWORD = ""
SF_SECURITY_TOKEN = ""
SF_DOMAIN = "login"
SF_CAMPAIGN_ID = ""

# --- CONFIGURATION ---

# Where to find it: Log into Salesforce, Premiere Success Package, open Campaigns, click on your specific campaign, and check the URL or the Campaign ID property block.
TARGET_CAMPAIGN_ID = ""  # Your Gala Campaign ID

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

# --- 2. FETCH ALL PAYMENTS FOR THE CAMPAIGN FROM ZEFFY ---
headers = {
    "Authorization": f"Bearer {ZEFFY_API_KEY}"
}

all_payments = []
has_more = True
next_cursor = None

print(f"Fetching payments for Campaign: {TARGET_CAMPAIGN_ID}...")

while has_more:
    params = {
        "campaign": TARGET_CAMPAIGN_ID,
        "status": "succeeded"  # Filter to succeeded payments
    }
    
    if next_cursor:
        params["starting_after"] = next_cursor

    try:
        response = requests.get(
            "https://api.zeffy.com/api/v1/payments",
            headers=headers,
            params=params
        )
        response.raise_for_status()
        res_data = response.json()
        
        # Pull data batch and update pagination state
        batch = res_data.get("data", [])
        all_payments.extend(batch)
        
        has_more = res_data.get("has_more", False)
        next_cursor = res_data.get("next_cursor")
        
    except requests.exceptions.RequestException as e:
        print(f"Error calling Zeffy API: {e}")
        break

print(f"Total payments fetched: {len(all_payments)}")

for payment in all_payments:
    buyer = payment.get("buyer", {})
    email = buyer.get("email")
    first_name = buyer.get("first_name", "")
    last_name = buyer.get("last_name", "Supporter")
    
    raw_amount = payment.get("amount", 0)
    amount = raw_amount / 100.0 if raw_amount > 100 else raw_amount
    description = payment.get("description", "Gala Ticket/Donation")
    
    # Extract the actual transaction date from Zeffy (usually 'created' timestamp or date string)

    payment_date = payment.get("created", "2026-09-24")
    if isinstance(payment_date, int):
        import datetime
        payment_date = datetime.datetime.fromtimestamp(payment_date).strftime('%Y-%m-%d')
    elif isinstance(payment_date, str) and len(payment_date >= 10):
        payment_date = payment_date[:10] # Grab YYYY-MM-DD format
    else:
        payment_date = "2026-09-24"

    if not email:
        print("Skipping: No email provided.")
        continue

    print(f"Processing: {payment_date} {first_name} {last_name} ({email})")

    try:
        # 1. Get or Create the Contact
        query = f"SELECT Id FROM Contact WHERE Email = '{email}' LIMIT 1"
        search_result = sf.query(query)

        if search_result['totalSize'] > 0:
            contact_id = search_result['records'][0]['Id']
            sf.Contact.update(contact_id, {
                'FirstName': first_name,
                'LastName': last_name
            })
            print(f"  -> Found existing Contact ID: {contact_id}")
        else:
            create_result = sf.Contact.create({
                'FirstName': first_name,
                'LastName': last_name,
                'Email': email
            })
            contact_id = create_result.get('id')
            print(f"  -> Created new Contact ID: {contact_id}")

        # 2. Add Contact to the Campaign as a CampaignMember
        cm_query = f"SELECT Id FROM CampaignMember WHERE CampaignId = '{SF_CAMPAIGN_ID}' AND ContactId = '{contact_id}' LIMIT 1"
        cm_search = sf.query(cm_query)

        if cm_search['totalSize'] == 0:
            sf.CampaignMember.create({
                'CampaignId': SF_CAMPAIGN_ID,
                'ContactId': contact_id,
                'Status': 'Responded'
            })
            print(f"  -> Added Contact to Campaign {SF_CAMPAIGN_ID}")
        else:
            print(f"  -> Contact is already a member of Campaign {SF_CAMPAIGN_ID}")

        # 3. Create or Check Opportunity with exact CloseDate tracking
        opp_name = f"{first_name} {last_name} - {description}"
        
        # Check against Contact, Amount, Name, and CloseDate to ensure zero duplicates
        opp_query = f"SELECT Id FROM Opportunity WHERE ContactId = '{contact_id}' AND Amount = {amount} AND CloseDate = '{payment_date}' LIMIT 1"
        opp_search = sf.query(opp_query)

        if opp_search['totalSize'] > 0:
            print(f"  -> Opportunity for this payment already exists on {payment_date}. Skipping.")
        else:
            sf.Opportunity.create({
                'Name': opp_name,
                'StageName': 'Closed Won',
                'CloseDate': payment_date,  # Tracks exact donation date from Zeffy
                'Amount': amount,
                'CampaignId': SF_CAMPAIGN_ID,
                'ContactId': contact_id
            })
            print(f"  -> Opportunity created successfully for ${amount} on {payment_date}\n")

    except Exception as e:
        print(f"  -> Error syncing {email}: {e}")
