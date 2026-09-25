import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext
import requests
from simple_salesforce import Salesforce, SalesforceAuthenticationFailed


class ZeffySFSyncApp:

  def __init__(self, root):
    self.root = root
    self.root.title("Zeffy to Salesforce Sync Tool")
    self.root.geometry("650x600")
    self.root.minsize(600, 550)

    # --- HARDCODED CREDENTIALS (Configure these once for them) ---
    self.SF_USERNAME = "your_salesforce_email@org.com"
    self.SF_PASSWORD = "your_salesforce_password"
    self.SF_SECURITY_TOKEN = "your_salesforce_security_token"
    self.SF_DOMAIN = "login"  

    # --- GUI LAYOUT ---
    title_label = tk.Label(
        root, text="Zeffy Gala Sync Dashboard", font=("Arial", 16, "bold")
    )
    title_label.pack(pady=10)

    # Frame for Inputs
    form_frame = tk.LabelFrame(
        root, text=" Configuration ", font=("Arial", 11, "bold"), padx=15, pady=15
    )
    form_frame.pack(fill="x", padx=20, pady=10)

    # Zeffy API Key Input
    tk.Label(
        form_frame, text="Zeffy API Key:", font=("Arial", 10)
    ).grid(row=0, column=0, sticky="w", pady=5)
    self.zeffy_entry = tk.Entry(form_frame, width=45, show="*")
    self.zeffy_entry.grid(row=0, column=1, sticky="w", pady=5, padx=5)

    # Salesforce Campaign ID Input
    tk.Label(
        form_frame, text="Salesforce Campaign ID:", font=("Arial", 10)
    ).grid(row=1, column=0, sticky="w", pady=5)
    self.campaign_entry = tk.Entry(form_frame, width=45)
    self.campaign_entry.grid(row=1, column=1, sticky="w", pady=5, padx=5)

    # Run Button
    self.run_button = tk.Button(
        root,
        text="Start Sync",
        font=("Arial", 12, "bold"),
        bg="#28a745",
        fg="white",
        padx=20,
        pady=5,
        command=self.start_sync_thread,
    )
    self.run_button.pack(pady=10)

    # Log/Console Output Area
    log_frame = tk.LabelFrame(
        root, text=" Live Status Log ", font=("Arial", 11, "bold"), padx=10, pady=10
    )
    log_frame.pack(fill="both", expand=True, padx=20, pady=10)

    self.log_area = scrolledtext.ScrolledText(
        log_frame, wrap=tk.WORD, font=("Courier", 9), bg="#f8f9fa"
    )
    self.log_area.pack(fill="both", expand=True)

  def log(self, message):
    """Appends messages to the GUI console log safely."""
    self.log_area.insert(tk.END, message + "\n")
    self.log_area.see(tk.END)

  def start_sync_thread(self):
    """Runs the sync in a separate thread so the GUI doesn't freeze."""
    zeffy_key = self.zeffy_entry.get().strip()
    campaign_id = self.campaign_entry.get().strip()

    if not zeffy_key or not campaign_id:
      messagebox.showerror(
          "Missing Fields",
          "Please enter both the Zeffy API Key and Campaign ID.",
      )
      return

    # Clear previous logs and lock button
    self.log_area.delete("1.0", tk.END)
    self.run_button.config(state=tk.DISABLED, bg="#6c757d")

    # Start backend process in background thread
    threading.Thread(
        target=self.run_sync_process, args=(zeffy_key, campaign_id), daemon=True
    ).start()

  def run_sync_process(self, zeffy_key, target_campaign_id):
    try:
      self.log("Connecting to Salesforce...")
      try:
        sf = Salesforce(
            username=self.SF_USERNAME,
            password=self.SF_PASSWORD,
            security_token=self.SF_SECURITY_TOKEN,
            domain=self.SF_DOMAIN,
        )
        self.log("-> Successfully connected to Salesforce.")
      except SalesforceAuthenticationFailed as e:
        self.log(f"-> Salesforce login failed: {e}")
        self.enable_button()
        return

      headers = {"Authorization": f"Bearer {zeffy_key}"}
      all_payments = []
      has_more = True
      next_cursor = None

      self.log(f"Fetching payments for Campaign: {target_campaign_id}...")

      while has_more:
        params = {"campaign": target_campaign_id, "status": "succeeded"}
        if next_cursor:
          params["starting_after"] = next_cursor

        response = requests.get(
            "https://api.zeffy.com/api/v1/payments",
            headers=headers,
            params=params,
        )
        response.raise_for_status()
        res_data = response.json()

        batch = res_data.get("data", [])
        all_payments.extend(batch)

        has_more = res_data.get("has_more", False)
        next_cursor = res_data.get("next_cursor")

      self.log(f"Total payments fetched: {len(all_payments)}\n")

      for payment in all_payments:
        buyer = payment.get("buyer", {})
        email = buyer.get("email")
        first_name = buyer.get("first_name", "")
        last_name = buyer.get("last_name", "Supporter")

        raw_amount = payment.get("amount", 0)
        amount = raw_amount / 100.0 if raw_amount > 100 else raw_amount
        description = payment.get("description", "Gala Ticket/Donation")

        if not email:
          self.log("Skipping: No email provided.")
          continue

        self.log(f"Processing: {first_name} {last_name} ({email})")

        # 1. Get or Create Contact
        query = f"SELECT Id FROM Contact WHERE Email = '{email}' LIMIT 1"
        search_result = sf.query(query)

        if search_result["totalSize"] > 0:
          contact_id = search_result["records"][0]["Id"]
          sf.Contact.update(
              contact_id, {"FirstName": first_name, "LastName": last_name}
          )
          self.log(f"  -> Found existing Contact ID: {contact_id}")
        else:
          create_result = sf.Contact.create({
              "FirstName": first_name,
              "LastName": last_name,
              "Email": email,
          })
          contact_id = create_result.get("id")
          self.log(f"  -> Created new Contact ID: {contact_id}")

        # 2. Campaign Member Mapping
        cm_query = f"SELECT Id FROM CampaignMember WHERE CampaignId = '{target_campaign_id}' AND ContactId = '{contact_id}' LIMIT 1"
        cm_search = sf.query(cm_query)

        if cm_search["totalSize"] == 0:
          sf.CampaignMember.create({
              "CampaignId": target_campaign_id,
              "ContactId": contact_id,
              "Status": "Responded",
          })
          self.log(f"  -> Added Contact to Campaign {target_campaign_id}")
        else:
          self.log(f"  -> Contact is already a member of Campaign.")

        # 3. Create Opportunity
        sf.Opportunity.create({
            "Name": f"{first_name} {last_name} - {description}",
            "StageName": "Closed Won",
            "CloseDate": "2026-09-24",
            "Amount": amount,
            "CampaignId": target_campaign_id,
            "ContactId": contact_id,
        })
        self.log(f"  -> Opportunity created successfully (${amount})\n")

      self.log("=== Sync execution completed successfully! ===")
      messagebox.Success(
          "Success", "The Zeffy sync has completed successfully!"
      )

    except Exception as e:
      self.log(f"\nCritical Error: {e}")
      messagebox.showerror("Error", f"An error occurred: {e}")

    finally:
      self.enable_button()

  def enable_button(self):
    self.run_button.config(state=tk.NORMAL, bg="#28a745")


if __name__ == "__main__":
  root = tk.Tk()
  app = ZeffySFSyncApp(root)
  root.mainloop()
