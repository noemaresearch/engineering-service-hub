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

## Step 1: Authenticate with Google Cloud

Ensure your local `gcloud` CLI is authenticated with the highly-privileged user account. This may require you to re-run these commands to target the new `global-states` project if you just created it.

```bash
gcloud auth login
gcloud auth application-default login
```

## Step 2: Clone the Repository

Clone the `engineering-service-hub` repository to your local machine.

```bash
git clone <repository_url>
cd engineering-service-hub
```

## Step 3: Configure the Deployment

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

## Step 4: Set up the Pulumi Environment

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

## Step 5: Deploy the Hub Infrastructure

Run the Pulumi deployment command. Pulumi will show you a preview of the resources to be created before asking for confirmation.

```bash
pulumi up
```

Review the plan and, when prompted, select `yes` to proceed. This process will take a few minutes as it creates a new GCP project and configures all the necessary resources.

---

## Step 6: Retrieve and Use Outputs

Once the deployment is complete, Pulumi will print the stack outputs. These are the critical values you will need to configure the CI/CD pipelines for your "Spoke" or tenant projects (like `engineering-service-core`).

**Example Outputs:**
```
Outputs:
    bootstrap_sa_email             : "org-cicd-bootstrap-sa@engineering-service-hub.iam.gserviceaccount.com"
    hub_project_id                 : "engineering-service-hub"
    workload_identity_provider_name: "projects/engineering-service-hub/locations/global/workloadIdentityPools/github-pool/providers/github-provider"
```

You will use these values to set the following secrets in the GitHub repositories that need to create new projects (e.g., in the `engineering-service-core` repository):

*   `GCP_BOOTSTRAP_SA_EMAIL`: The `bootstrap_sa_email` output.
*   `GCP_BOOTSTRAP_WIF_PROVIDER`: The `workload_identity_provider_name` output.

**Bootstrap is now complete.** Your platform's identity hub is live, and your CI/CD pipelines can now run in a fully-automated and secure manner.

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
