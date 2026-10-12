# Security Configuration & CIS Compliance Tool

A single-file Streamlit app for walking a client through a hardening checklist,
recording per-control compliance status + evidence, and viewing a live
compliance dashboard.

## Run it

```bash
pip install -r requirements.txt
streamlit run security_config_dashboard.py
```

It opens at `http://localhost:8501`.

## How it's built

- **Checklist source**: For technologies with a published CIS Benchmark
  (Linux, Windows Server/AD, AWS/Azure/GCP, Docker/Kubernetes), the controls
  are organized under the same category structure CIS uses (Account Policies,
  Logging & Auditing, Network Configuration, etc.) with a rough benchmark
  section reference next to each item.
- **No CIS benchmark available**: For technologies without a formal CIS
  Benchmark (e.g. a custom web app/API), a generic best-practice checklist is
  used instead, built from widely used frameworks (OWASP ASVS/Top 10, NIST,
  general secure-config practice).
- **Before client sign-off**: treat the reference column as a pointer, not a
  verbatim quote — pull the actual current CIS Benchmark PDF for the specific
  OS/version/cloud provider in scope (from cisecurity.org, free with a CIS
  account) and confirm exact control numbering and remediation steps, since
  CIS updates benchmarks per OS/version release.

## Using it with a client

1. Enter the client/engagement name and reviewer in the sidebar.
2. Pick the technology being assessed.
3. Go through each category, set a status per control:
   - **Compliant** / **Non-Compliant** / **Compensating Control** /
     **Not Applicable** / **Not Reviewed**
4. Add evidence or a deviation justification in the notes field per control.
5. Switch to the **Compliance Dashboard** tab to see:
   - Overall compliance %
   - Status breakdown (pie chart)
   - Compliance % by category (bar chart)
   - A live table of open non-compliant items (remediation tracker)
6. Export progress to CSV anytime (sidebar or dashboard tab) — you can
   re-upload that CSV later to resume the assessment.

## Cloud persistence setup (optional, recommended for Streamlit Cloud)

Streamlit Community Cloud's filesystem is ephemeral — without this, progress
only survives via manual CSV export/import. This adds automatic save/load
per client+technology, backed by a Google Sheet.

1. **Create a Google Sheet** (e.g. "CIS Compliance Data") and copy its ID
   from the URL: `https://docs.google.com/spreadsheets/d/<SHEET_ID>/edit`.
2. **Create a Google Cloud service account**:
   - Go to console.cloud.google.com → create/select a project.
   - Enable the "Google Sheets API" and "Google Drive API".
   - Go to IAM & Admin → Service Accounts → Create service account.
   - Create a JSON key for it and download it.
3. **Share the Sheet** with the service account's email address (it looks
   like `something@your-project.iam.gserviceaccount.com`) as an Editor.
4. **Add secrets** — in Streamlit Cloud, go to your app → Settings → Secrets,
   and paste (values from the downloaded JSON key):

   ```toml
   [gsheets]
   sheet_id = "your-sheet-id-here"

   [gcp_service_account]
   type = "service_account"
   project_id = "your-project-id"
   private_key_id = "..."
   private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
   client_email = "something@your-project.iam.gserviceaccount.com"
   client_id = "..."
   auth_uri = "https://accounts.google.com/o/oauth2/auth"
   token_uri = "https://oauth2.googleapis.com/token"
   auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
   client_x509_cert_url = "..."
   ```

   For local runs, put the same content in `.streamlit/secrets.toml` instead
   (add that path to `.gitignore` — never commit real credentials).

5. Redeploy/rerun the app. The sidebar will show "☁️ Cloud persistence
   connected" and add **Save to cloud** / **Load from cloud** buttons. Each
   client + technology combination is saved to its own tab in the Sheet, so
   multiple engagements can share one Sheet without colliding.

Without this setup, the app runs exactly as before, using the CSV
export/import buttons for persistence.

## Extending it

All checklist content lives in the `CHECKLISTS` dict near the top of
`security_config_dashboard.py`. To add a new technology, add a new key with a
list of tuples: `(item_id, category, control_text, reference)`. The rest of
the UI (checklist rendering, dashboard, export) picks it up automatically.
