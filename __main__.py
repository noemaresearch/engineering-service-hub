import pulumi
import pulumi_gcp as gcp

# --- Configuration ---
config = pulumi.Config()

# The ID for the new Hub project to be created.
hub_project_id = config.require("gcp_project") 

# Organization/Folder details for project creation.
billing_account_id = config.require("billing_account_id")
folder_id = config.require("folder_id")

# GitHub organization to trust for Workload Identity Federation.
github_org = config.require("github_org")

# --- Resource Naming ---
bootstrap_sa_id = "org-cicd-bootstrap-sa"
wif_pool_id = "github-pool"
wif_provider_id = "github-provider"

# --- 1. Create the Hub GCP Project ---
hub_project = gcp.organizations.Project("hub-project",
    project_id=hub_project_id,
    name="Engineering Service Hub",
    folder_id=folder_id,
)

# --- 2. Link Project to Billing Account ---
project_billing = gcp.billing.ProjectBillingInfo("hub-project-billing",
    project=hub_project.project_id,
    billing_account=billing_account_id,
    opts=pulumi.ResourceOptions(depends_on=[hub_project])
)

# --- 3. Enable Required APIs on the Hub Project ---
# We enable APIs here that are needed to manage resources within this Hub project.
apis = [
    "iam.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "iamcredentials.googleapis.com",
    "sts.googleapis.com",
]

enabled_apis = []
for api in apis:
    enabled_api = gcp.projects.Service(f"enable-{api.split('.')[0]}-api",
        service=api,
        project=hub_project.project_id,
        disable_on_destroy=False,
        opts=pulumi.ResourceOptions(depends_on=[project_billing])
    )
    enabled_apis.append(enabled_api)

# --- 4. Create the Bootstrap Service Account in the Hub Project ---
bootstrap_sa = gcp.serviceaccount.Account("bootstrap-sa",
    account_id=bootstrap_sa_id,
    display_name="Organization CI/CD Bootstrap Service Account",
    project=hub_project.project_id,
    opts=pulumi.ResourceOptions(depends_on=enabled_apis)
)

# --- 5. Grant Organization-Level Permissions to the Bootstrap SA ---
# These roles allow the SA to create new projects and manage billing/IAM for them.
org_level_roles = [
    "roles/resourcemanager.projectCreator",
    "roles/billing.user",
    "roles/iam.workloadIdentityPoolAdmin",
    "roles/iam.serviceAccountAdmin",
    "roles/serviceusage.serviceUsageAdmin",
]

for role in org_level_roles:
    gcp.organizations.IAMMember(f"bootstrap-sa-org-binding-{role.replace('.', '-')}",
        org_id=folder_id, # Assuming we are granting roles at the folder level
        role=role,
        member=pulumi.Output.concat("serviceAccount:", bootstrap_sa.email)
    )

# --- 6. Create the Workload Identity Federation Pool and Provider ---
wif_pool = gcp.iam.WorkloadIdentityPool("wif-pool",
    workload_identity_pool_id=wif_pool_id,
    display_name="GitHub Actions WIF Pool",
    project=hub_project.project_id,
    opts=pulumi.ResourceOptions(depends_on=enabled_apis)
)

wif_provider = gcp.iam.WorkloadIdentityPoolProvider("wif-provider",
    workload_identity_pool_id=wif_pool.workload_identity_pool_id,
    workload_identity_pool_provider_id=wif_provider_id,
    display_name="GitHub OIDC Provider",
    project=hub_project.project_id,
    oidc=gcp.iam.WorkloadIdentityPoolProviderOidcArgs(
        issuer_uri="https://token.actions.githubusercontent.com",
    ),
    attribute_mapping={
        "google.subject": "assertion.sub",
        "attribute.actor": "assertion.actor",
        "attribute.repository": "assertion.repository",
    },
    # This condition restricts which GitHub repos can get a token.
    # We scope it to the entire specified GitHub organization.
    attribute_condition=f"attribute.repository.starts_with('repos/{github_org}/')",
    opts=pulumi.ResourceOptions(depends_on=[wif_pool])
)

# --- 7. Bind WIF to the Bootstrap Service Account ---
# This is the crucial step that allows GitHub Actions to impersonate the Bootstrap SA.
gcp.serviceaccount.IAMMember("wif-bootstrap-sa-binding",
    service_account_id=bootstrap_sa.name, # This is the full name of the SA resource
    role="roles/iam.workloadIdentityUser",
    member=pulumi.Output.concat(
        "principalSet://iam.googleapis.com/",
        wif_pool.name.apply(lambda name: name.replace("/", "/locations/global/workloadIdentityPools/")),
        f"/attribute.repository_owner/{github_org}"
    ),
    opts=pulumi.ResourceOptions(depends_on=[bootstrap_sa, wif_provider])
)

# --- Outputs ---
pulumi.export("hub_project_id", hub_project.project_id)
pulumi.export("bootstrap_sa_email", bootstrap_sa.email)
pulumi.export("workload_identity_provider_name", wif_provider.name)
