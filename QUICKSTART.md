# Quickstart: Bootstrapping the Engineering Service Hub

This guide provides the step-by-step instructions for a privileged operator (e.g., a GCP Organization Administrator) to perform the **one-time setup** of the Engineering Service Hub.

## Purpose

The goal of this process is to create the central identity and trust foundation for the entire engineering service platform. After this one-time setup, all subsequent project and environment creation will be fully automated via CI/CD.

## Prerequisites

1.  **GCP Organization**: You must have a Google Cloud Organization.
2.  **GCP Folder (Recommended)**: It's best practice to create a dedicated GCP Folder to contain all projects related to the Engineering Service. You will need its ID (e.g., `folders/123456789012`).
3.  **GCP Billing Account**: You must have an active GCP Billing Account and its ID (e.g., `01A2B3-C4D5E6-F7G8H9`).
4.  **GitHub Organization**: You must have a GitHub Organization, and you will need its exact name (e.g., `my-cool-company`).
5.  **Required Local Tools**:
    *   [Google Cloud SDK (`gcloud`)](https://cloud.google.com/sdk/docs/install)
    *   [Pulumi CLI](https://www.pulumi.com/docs/get-started/install/)
6.  **Required Permissions**: The user running these commands must be authenticated with `gcloud` and have the following permissions at the GCP Organization or Folder level:
    *   `roles/resourcemanager.projectCreator`
    *   `roles/billing.user`
    *   `roles/iam.workloadIdentityPoolAdmin`
    *   `roles/iam.serviceAccountAdmin`
    *   `roles/serviceusage.serviceUsageAdmin`

---

## Step 0: (Recommended) Set Up a Remote State Backend

By default, Pulumi stores your infrastructure state on your local machine. For a foundational project like this, it is highly recommended to use a remote backend to protect the state file and enable collaboration.

These commands will create a dedicated GCP project and a GCS bucket to store your state.

1.  **Create the State Project**:
    ```bash
    gcloud projects create global-states --folder=YOUR_NUMERIC_FOLDER_ID
    ```
    *(Replace `YOUR_NUMERIC_FOLDER_ID` with the ID of the folder where you want to place this project, e.g., your `engineering-platform` folder ID).*

2.  **Set Your Active Project**:
    ```bash
    gcloud config set project global-states
    ```

3.  **Create the GCS Bucket**:
    *Note: GCS bucket names must be globally unique. You may need to change this name slightly.*
    ```bash
    gsutil mb -p global-states gs://global-pulumi-state-bucket
    ```

4.  **Enable Versioning (Recommended)**:
    This protects against accidental state deletion or corruption.
    ```bash
    gsutil versioning set on gs://global-pulumi-state-bucket
    ```

You will use this bucket name later when you log in to Pulumi.

---

## Step 1: Manual Permissions Setup (One-Time)

Before running any automation, a user with **GCP Organization Admin** privileges must grant two key roles to the primary operator (the user who will run the initial `pulumi up`).

**Provide these two commands to your Organization Administrator:**

1.  **Grant Organization Admin to Operator**: This allows the operator to create projects, folders, and manage IAM.
    ```bash
    gcloud organizations add-iam-policy-binding YOUR_ORGANIZATION_ID \
      --member="user:YOUR_OPERATOR_EMAIL" \
      --role="roles/resourcemanager.organizationAdmin"
    ```
    *(Note: Replace `YOUR_ORGANIZATION_ID` and `YOUR_OPERATOR_EMAIL`)*

2.  **Grant Billing User to Operator**: This is crucial. It allows the operator to link the new Hub project to the billing account.
    ```bash
    gcloud beta billing accounts add-iam-policy-binding YOUR_BILLING_ACCOUNT_ID \
      --member="user:YOUR_OPERATOR_EMAIL" \
      --role="roles/billing.user"
    ```
    *(Note: Replace `YOUR_BILLING_ACCOUNT_ID` and `YOUR_OPERATOR_EMAIL`)*

---

## Step 2: Authenticate with Google Cloud

Ensure your local `gcloud` CLI is authenticated with the highly-privileged user account. This may require you to re-run these commands to target the new `global-states` project if you just created it.

```bash
gcloud auth login
gcloud auth application-default login
```

## Step 3: Clone the Repository

Clone the `engineering-service-hub` repository to your local machine.

```bash
git clone <repository_url>
cd engineering-service-hub
```

## Step 4: Configure the Deployment

Open the `Pulumi.dev.yaml` file and replace the placeholder values with your actual information.

**Example `Pulumi.dev.yaml`:**
```yaml
config:
  gcp:project: engineering-service-hub
  engineering-service-hub:billing_account_id: 01A2B3-C4D5E6-F7G8H9
  engineering-service-hub:folder_id: '123456789012'
  engineering-service-hub:github_org: my-cool-company
```

*   `gcp:project`: This will be the ID of the new GCP project created to act as the Hub. `engineering-service-hub` is a good default.
*   `billing_account_id`: Your GCP Billing Account ID.
*   `folder_id`: The ID of the GCP Folder where the hub project will be created.
*   `github_org`: Your organization's name on GitHub.

## Step 5: Set up the Pulumi Environment

1.  **Create a Python Virtual Environment**:
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

2.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

3.  **Log in to Pulumi**:
    Follow the prompts to log in to your desired Pulumi backend. For local state, you can use `pulumi login --local`. 

    **To use the GCS backend you just created, run:**
    ```bash
    pulumi login gs://global-pulumi-state-bucket
    ```

## Step 6: Deploy the Hub Infrastructure

Run the Pulumi deployment command. Pulumi will show you a preview of the resources to be created before asking for confirmation.

```bash
pulumi up
```

Review the plan and, when prompted, select `yes` to proceed. This process will take a few minutes as it creates a new GCP project and configures the WIF Pool and Provider.

---

## Step 6: Manually Create and Configure the Bootstrap Service Account

After the Pulumi deployment is complete, a one-time manual setup is required to create the high-privilege service account that your CI/CD pipelines will use.

**Provide these commands to your GCP Organization Administrator.**

*(Note: Replace `YOUR_FOLDER_ID` and `YOUR_BILLING_ACCOUNT_ID` with the actual IDs used in your configuration.)*

1.  **Create the Service Account**:
    This account is created within the new `engineering-service-hub` project.
    ```bash
    gcloud iam service-accounts create engineering-service-org-sa \
      --project="engineering-service-hub" \
      --display-name="Organization CI/CD Bootstrap Service Account"
    ```

2.  **Grant Permissions to the Service Account**:
    These commands grant the necessary permissions at the Folder and Billing Account levels.
    ```bash
    # Grant permission to create new projects
    gcloud resource-manager folders add-iam-policy-binding YOUR_FOLDER_ID \
      --member="serviceAccount:engineering-service-org-sa@engineering-service-hub.iam.gserviceaccount.com" \
      --role="roles/resourcemanager.projectCreator"

    # Grant permission to manage service accounts in new projects
    gcloud resource-manager folders add-iam-policy-binding YOUR_FOLDER_ID \
      --member="serviceAccount:engineering-service-org-sa@engineering-service-hub.iam.gserviceaccount.com" \
      --role="roles/iam.serviceAccountAdmin"

    # Grant permission to manage WIF pools
    gcloud resource-manager folders add-iam-policy-binding YOUR_FOLDER_ID \
      --member="serviceAccount:engineering-service-org-sa@engineering-service-hub.iam.gserviceaccount.com" \
      --role="roles/iam.workloadIdentityPoolAdmin"

    # Grant permission to enable APIs on new projects
    gcloud resource-manager folders add-iam-policy-binding YOUR_FOLDER_ID \
      --member="serviceAccount:engineering-service-org-sa@engineering-service-hub.iam.gserviceaccount.com" \
      --role="roles/serviceusage.serviceUsageAdmin"

3.  **Grant Billing Permission to Service Account (Manual)**:
    This must be run by someone with permissions on the billing account (e.g., your Organization Admin). This allows the service account to link all *future* projects to billing.
    ```bash
    gcloud beta billing accounts add-iam-policy-binding YOUR_BILLING_ACCOUNT_ID \
      --member="serviceAccount:engineering-service-org-sa@engineering-service-hub.iam.gserviceaccount.com" \
      --role="roles/billing.user"
    ```

4.  **Connect GitHub Actions to the Service Account**:
    This final binding allows the WIF provider to impersonate the service account. The numeric project ID and organization name come from your setup.
    ```bash
    gcloud iam service-accounts add-iam-policy-binding "engineering-service-org-sa@engineering-service-hub.iam.gserviceaccount.com" \
      --project="engineering-service-hub" \
      --role="roles/iam.workloadIdentityUser" \
      --member="principalSet://iam.googleapis.com/projects/687854479837/locations/global/workloadIdentityPools/github-pool/attribute.repository_owner/noemaresearch"
    ```

---

## Step 7: Configure Your CI/CD Pipelines

The setup is now complete. The final step is to configure the GitHub secrets in the repositories that will be performing automated deployments (e.g., `engineering-service-core`).

**In your `engineering-service-core` GitHub repository, set the following secrets:**

1.  `GCP_WORKLOAD_IDENTITY_PROVIDER`:
    *   **Value**: The `workload_identity_provider_name` output from the `pulumi up` command.
    *   **Example**: `projects/687854479837/locations/global/workloadIdentityPools/github-pool/providers/github-provider`

2.  `GCP_SERVICE_ACCOUNT_EMAIL`:
    *   **Value**: The full email of the service account you just created.
    *   **Example**: `engineering-service-org-sa@engineering-service-hub.iam.gserviceaccount.com`

Your CI/CD pipeline in `engineering-service-core` is now equipped to authenticate with GCP and create new, fully-configured environments on demand.

---

## Step 8: Create and Configure a Deployment Environment in GitHub

For a true multi-tenant setup, we will create a dedicated GitHub Environment to hold the secrets for our new deployments, keeping them separate from the original `dev` environment.

Run the following commands to create a new environment called `multi-tenant-dev` and populate it with all the necessary secrets.

*(Note: You will need to have your API keys and Pulumi passphrase available as environment variables in your local shell, e.g., `export ANTHROPIC_API_KEY=...`)*

```bash
# --- Step 1: Create the new GitHub Environment ---
gh api \
  -X PUT \
  -H "Accept: application/vnd.github+json" \
  /repos/noemaresearch/engineering-service-core/environments/multi-tenant-dev

# --- Step 2: Set All Secrets for the 'multi-tenant-dev' Environment ---

# Set WIF Provider (from Hub output)
gh secret set GCP_WORKLOAD_IDENTITY_PROVIDER \
  --env "multi-tenant-dev" \
  --body "projects/687854479837/locations/global/workloadIdentityPools/github-pool/providers/github-provider" \
  --repo noemaresearch/engineering-service-core

# Set Bootstrap Service Account Email (from manual step)
gh secret set GCP_SERVICE_ACCOUNT_EMAIL \
  --env "multi-tenant-dev" \
  --body "engineering-service-org-sa@engineering-service-hub.iam.gserviceaccount.com" \
  --repo noemaresearch/engineering-service-core

# Set the new Project ID for this environment
gh secret set GCP_PROJECT_ID \
  --env "multi-tenant-dev" \
  --body "noema-core-multi-tenant-dev" \
  --repo noemaresearch/engineering-service-core

# Set Pulumi State Bucket (can be reused)
gh secret set PULUMI_GCS_BUCKET \
  --env "multi-tenant-dev" \
  --body "engineering-state-bucket" \
  --repo noemaresearch/engineering-service-core

# Set Artifact Registry Repo ID (can be reused)
gh secret set ARTIFACT_REPO_ID \
  --env "multi-tenant-dev" \
  --body "engineering-service-images" \
  --repo noemaresearch/engineering-service-core

# --- Set Secrets from Your Local Environment Variables ---

# Set Pulumi Passphrase
echo "$PULUMI_CONFIG_PASSPHRASE" | gh secret set PULUMI_CONFIG_PASSPHRASE \
  --env "multi-tenant-dev" \
  --repo noemaresearch/engineering-service-core

# Set Anthropic API Key
echo "$ANTHROPIC_API_KEY" | gh secret set ANTHROPIC_API_KEY \
  --env "multi-tenant-dev" \
  --repo noemaresearch/engineering-service-core

# Set Gemini API Key
echo "$GEMINI_API_KEY" | gh secret set GEMINI_API_KEY \
  --env "multi-tenant-dev" \
  --repo noemaresearch/engineering-service-core

# Set OpenAI API Key
echo "$OPENAI_API_KEY" | gh secret set OPENAI_API_KEY \
  --env "multi-tenant-dev" \
  --repo noemaresearch/engineering-service-core
```

Your CI/CD pipeline in `engineering-service-core` is now equipped to authenticate with GCP and create new, fully-configured environments on demand by targeting the `multi-tenant-dev` environment.

---

## Troubleshooting

### `pulumi login` Fails with `oauth2: "invalid_grant"`

If you see an error similar to this when running `pulumi login gs://...`:

```
error: problem logging in: read ".pulumi/meta.yaml": blob (key ".pulumi/meta.yaml") (code=Unknown): Get "...": oauth2: "invalid_grant" "reauth related error (invalid_rapt)"
```

This is **not** a Pulumi error. It means your local Google Cloud authentication token has expired.

**Solution:** Refresh your `gcloud` credentials by re-running the authentication commands:

```bash
gcloud auth login
gcloud auth application-default login
```

After completing the browser login, try the `pulumi login` command again. It should now succeed.
