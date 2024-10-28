# Common (infrastructure)

This readme details setup for namespace-wide infrastructure.

## Secrets
[Kubernetes Secrets](https://kubernetes.io/docs/concepts/configuration/secret/) 
are stored in the `flights-pipeline-prod` and `flights-pipeline-dev` namespace,
and accessible by any services deployed in those namespaces.  Secrets can be
manually created with [`kubectl create secret`](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_create/kubectl_create_secret/).
For most services, we use generic (Opaque) secrets ([`kubectl create secret generic`](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_create/kubectl_create_secret_generic/)).

Typically, secrets are accessed by mounting them as environment variables in a Kubernetes resource.
These environment varibles are not passed in via CICD, rather mounted directly from a named secret.

For example:
```yaml
- name: MY_TOKEN
  valueFrom:
    secretKeyRef:
      name: my-k8s-secret-name
      key: SOME_KEY_IN_SECRET
```

Note that secrets are base64 encoded when retrieved via the CLI, but decoded when injected into 
environment variables.

For example, to retrieve and inspect the above secret:
```bash
kubectl get secret my-k8s-secret-name -o json -n my-namespace | jq '.data.MY_TOKEN' | xargs echo | base64 -d
```

### Spire token
The Spire Airsafe API token is stored as a kubernetes secret, and loaded into the
`spire-ingest-api-scraper` service.

#### Setup
Running the following will manually load the Spire Airsafe token into a secret by
passing the literal key-value to store as a secret.

```bash
SPIRE_AIRSAFE_API_TOKEN=token_value && kubectl create secret generic spire-airsafe-api-secret --from-literal=API_TOKEN=$(SPIRE_AIRSAFE_API_TOKEN) -n flights-pipeline-<prod/dev>
```

### GCP Service Account
Typically, services running in Kubernetes can authenticate to GCP services without the explicit
use of an access token.  i.e. python clients for GCP services (e.g. GCS, PubSub, etc...) can be
instantiated without an explicit token.  If no token is provided, the client will communicate
with a GCP metadata server, which is automagically configured and running in k8s,
and retrieve from that metadata server an access token authenticated to the service account
for the k8s namespace.

See the [.cloud/auth.tf terraform manifest](../.cloud/auth.tf) for the workload-identify-federation setup of GCP service account to the k8s service account.

See the [SRE repo's kubernetes README](https://github.com/contrailcirrus/sre/tree/main/kubernetes#authing-pods-to-gcp-resources) for information on how workload identify federation works between GCP Auth <> k8s cluster.

See [REF](https://cloud.google.com/kubernetes-engine/docs/concepts/workload-identity#metadata_server) for more information on the k8s metadata server.

#### Setup

**First**, identify the GCP service account associated with the target namespace.
Here, our target namespace is `flights-pipeline-<dev/prod>`.
Note that by convention, we use the same GCP service account for both dev and prod.

The easiest way to identify the service account is via inspection:
```bash
kubectl get serviceaccount -n flights-pipeline-prod
```
```bash
kubectl describe serviceaccount flights-pipeline-default-sa -n flights-pipeline-prod
```

The GCP service account bound to the k8s namespace's service account will show up in
```text
...
Annotations:         iam.gke.io/gcp-service-account: flights-pipeline@contrails-301217.iam.gserviceaccount.com
```

**Next**, create a service account key in the GCP console.
This can be done by navigating to `IAM > Service Accounts` and searching for the above GCP svc account.
Once in the svc acct page, navigate to `KEYS` and click `ADD KEY > Create new key > JSON (Create)`.
This will download a JSON key to your local machine.

**Next**, load the key into a kubernetes secret in both dev and prod namespaces.
Running the following will load the GCP service account key file into a k8s secret.
```bash
kubectl create secret generic gcp-service-account-key --from-file=GCP_SVC_ACCT_KEY=<PATH_TO_FILE> -n flights-pipeline-<dev/prod>
```

**Lastly**, permanently delete the local JSON file from your machine.

### CloudSQL (PSDB) - flight emissions report database
User credentials for accessing the flight emissions report (FER) SQL database are stored as kubernetes secrets in the `flights-pipeline-<dev>/<prod>` namespace.

### Setup
Two secrets are stored for FER DB access.
(1) password for read-only user (`internal_user_ro`)
(2) password for read-write user (`internal_user_rw`)

Each secret is minted with the following command, substituting for respective users and environments.

```bash
PASSWORD=my_password && kubectl create secret generic fer-psdb-interal-user-<ro/rw>-pwd-secret --from-literal=PASSWORD=$(PASSWORD) -n flights-pipeline-<prod/dev>
```

The secret can be accessed in a k8s manifest by injecting an env var from this secret.

e.g.
```yaml
- name: PSDB_PASS
  valueFrom:
    secretKeyRef:
      name: fer-psdb-interal-user-ro-pwd-secret
      key: PASSWORD
```