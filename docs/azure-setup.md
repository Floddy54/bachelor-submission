# Azure Setup Guide — bachelor-anti-bad

This guide walks you through setting up Azure Blob Storage to replace the local
disk + SCP sync for the Anti-BAD dashboard. Follow the steps in order. When you
finish, come back and we'll adapt `dashboard/server.py`, `dashboard/index.html`
and the SLURM scripts to use it.

## Chosen architecture

- **Service**: Azure Blob Storage (one storage account, one private container).
- **Subscription**: **Pay-As-You-Go** (personal), not Azure for Students.
  Vetle's student subscription has an unusually tight region allow-list
  (Norway East, North Europe and West Europe all blocked on 2026-04-20), so
  we switched to a personal PAYG subscription to get free region choice.
  A $10 monthly budget with alerts is set up in Cost Management as a safety
  net — real workload cost is ~$0.25/month.
- **Region**: **Norway East** (closest to Kristiania + Norwegian data
  residency, no restrictions on PAYG).
- **Redundancy**: LRS (locally-redundant, cheapest — fine for thesis data).
- **Access tier**: Hot (frequent reads from the dashboard).
- **Auth**: storage account connection string, stored in `.secrets/` (git-ignored).
- **HPC upload**: `azcopy sync` at the end of each SLURM job.
- **Local dashboard**: reads blobs directly via `azure-storage-blob` Python SDK.

## Cost sanity check (Pay-As-You-Go, $10 budget)

Norway East, Standard LRS, Hot tier:

- Storage: ~0.021 USD / GB / month. 10 GB ≈ **$0.21/month**.
- Write operations: ~0.065 USD per 10,000. A SLURM job that uploads ~500 files
  = ~0.003 USD per run.
- Read operations: ~0.005 USD per 10,000. Dashboard page load ≈ fractions of a
  cent.
- Egress (blob download to your laptop): first 100 GB/month free on student
  accounts, then cheap.

**Bottom line**: for logs + CSVs + small JSON datasets you'll spend pennies per
month. $100 lasts the entire thesis comfortably.

---

## Step 1 — Create a Pay-As-You-Go subscription

Student subscriptions proved too restrictive on region choice, so we use a
personal PAYG account. First-time signup includes $200 credit + 12 months
of free services (blob storage has a 5 GB free tier in that year).

1. Go to <https://azure.microsoft.com/en-us/pricing/purchase-options/pay-as-you-go/>.
2. Sign in with a **personal** Microsoft account (gmail/outlook) — keep
   this separate from your Kristiania login so the student credit remains
   usable elsewhere later.
3. Complete identity + credit card verification. Country: Norway.
4. Subscription name: "Pay-As-You-Go" (default).
5. You land in the Azure Portal: <https://portal.azure.com>.

## Step 1b — Set a $10 budget with alerts

PAYG does **not** hard-stop spending at a budget — it only alerts. Set up
alerts before creating any resources so you can't get blindsided.

1. Portal → **Cost Management + Billing** → **Cost Management** → **Budgets**.
2. Scope: Pay-As-You-Go subscription → **+ Add**.
3. Fields:
   - Name: `thesis-hard-cap`
   - Reset period: **Monthly**
   - Expiration: 2027-12-31 (anything far in the future)
   - Budget amount: **10** USD
4. Alerts: email `vetlehostlund@gmail.com` at **50%**, **80%**, **100%**.
5. Save.

At the expected ~$0.25/month spend, you should never see an alert. If you
do, check the portal — something unexpected is running.

## Step 2 — Create a Resource Group

A resource group is a logical folder for everything in this project, so you
can delete it all at once if you need to reset.

1. Portal → search "Resource groups" → **+ Create**.
2. Subscription: **Pay-As-You-Go**.
3. Resource group name: `bachelor-anti-bad`.
4. Region: **Norway East**.
5. **Review + create** → **Create**.

> If you had a `bachelor-anti-bad` group in your old student subscription,
> you can leave it — it's on a different subscription and won't cost
> anything. Eventually you can delete it via the student sub's portal.

## Step 3 — Create the Storage Account

1. Portal → search "Storage accounts" → **+ Create**.
2. **Basics** tab:
   - Subscription: **Pay-As-You-Go**
   - Resource group: `bachelor-anti-bad`
   - Storage account name: `antibad<yourinitials>` (must be globally unique,
     3–24 chars, lowercase letters/digits only). Example: `antibadvh`.
   - Region: **Norway East**
   - Primary service: *Azure Blob Storage or Azure Data Lake Storage Gen 2*
   - Performance: **Standard**
   - Redundancy: **LRS (Locally-redundant storage)**
3. **Advanced** tab: leave defaults. (Hot is default; secure transfer required
   is on; min TLS 1.2 is fine.)
4. **Networking** tab: leave "Enable public access from all networks" — you'll
   need this so the dashboard can read from your laptop and azcopy from HPC.
5. **Data protection** tab: you can turn off blob soft-delete and versioning
   to keep costs minimal for a thesis (you have git + HPC as backup).
6. **Review + create** → **Create**. Takes ~30 seconds.

## Step 4 — Create the Blob Container

1. Open the storage account you just created.
2. Left sidebar → **Data storage** → **Containers**.
3. **+ Container**:
   - Name: `anti-bad`
   - Anonymous access level: **Private (no anonymous access)**
4. Create.

We'll use one container and organise with virtual folders (blob prefixes).
Because the project is shared by a 4-person thesis group (each with their
own HPC account), the top level of the container is partitioned by **member
name**, so nobody's `.out` / `.err` logs collide:

```
anti-bad/
├── vetle/
│   ├── logs/                      ← scripts/slurm/logs/
│   ├── results/general/           ← experiments/results/general/
│   ├── submission/                ← experiments/submission/
│   └── data/processed/task1/      ← data/processed/task1/
├── alice/
│   └── ... (same shape)
├── bob/
│   └── ... (same shape)
└── carol/
    └── ... (same shape)
```

Each member sets `export MEMBER=<their-name>` on both their HPC and their
laptop; SLURM scripts and `server.py` build blob paths as
`${MEMBER}/logs/...`, `${MEMBER}/results/...` etc. The dashboard will read
across all member prefixes and let you filter by owner.

## Step 5 — Grab the Connection String

1. Storage account → **Security + networking** → **Access keys**.
2. Click **Show** next to `key1` → copy the whole **Connection string** value.
   It looks like:
   `DefaultEndpointsProtocol=https;AccountName=antibadvh;AccountKey=...;EndpointSuffix=core.windows.net`

⚠ Treat this like a password — it grants full control of the storage account.
Do **not** paste it in chat, commit it, or share it on GitHub.

## Step 6 — Save the Connection String Locally and on HPC

### On your laptop — Windows PowerShell (Vetle's env)

```powershell
cd C:\path\to\bachelor-anti-bad
mkdir .secrets -ErrorAction SilentlyContinue
Set-Content -Path .secrets\azure_connection_string -Value 'PASTE_CONNECTION_STRING_HERE' -NoNewline -Encoding ascii
# sanity check — should print the connection string length with no trailing newline
(Get-Content .secrets\azure_connection_string -Raw).Length
```

> `-NoNewline` is important: Azure SDKs don't strip trailing whitespace, so
> a stray `\n` will cause authentication failures. `-Encoding ascii` avoids
> the UTF-8 BOM PowerShell adds by default, which would also break auth.

### On your laptop — macOS / Linux / WSL bash

```bash
cd /path/to/bachelor-anti-bad
mkdir -p .secrets
printf '%s' 'PASTE_CONNECTION_STRING_HERE' > .secrets/azure_connection_string
chmod 600 .secrets/azure_connection_string
```

`.secrets/` is already in `.gitignore`, so this won't be committed. On Windows
there's no direct equivalent of `chmod 600` — the file being in a gitignored
folder on your personal machine is sufficient protection for a thesis project.

### On HPC (for azcopy uploads)

```bash
ssh vetle@10.10.15.10
cd ~/bachelor-anti-bad
mkdir -p .secrets
printf '%s' 'PASTE_CONNECTION_STRING_HERE' > .secrets/azure_connection_string
chmod 600 .secrets/azure_connection_string
```

Alternatively (more secure), we can switch to a **SAS token** with write-only
permissions for HPC later — ping me once the basic flow works.

## Step 7 — Install Tools

### On your laptop (inside `bachelorenv`)

`azure-storage-blob` and `python-dotenv` are already pinned in
`environment.yml` under the pip section. Rebuild the env once to pull them:

```bash
conda env update -f environment.yml --prune
conda activate bachelorenv
python -c "import azure.storage.blob, dotenv; print('ok')"
```

Group members who clone the repo fresh and run `conda env create -f
environment.yml` will pick them up automatically — no extra step.

### On HPC — install AzCopy

```bash
ssh vetle@10.10.15.10
mkdir -p ~/bin && cd ~/bin
wget -O azcopy.tar.gz https://aka.ms/downloadazcopy-v10-linux
tar -xf azcopy.tar.gz --strip-components=1 --wildcards '*/azcopy'
rm azcopy.tar.gz
chmod +x azcopy
# make sure ~/bin is on PATH
echo 'export PATH="$HOME/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
azcopy --version
```

## Step 8 — Smoke Test

### Laptop — upload a test file with Python

Save `dashboard/smoke_test.py`:

```python
from pathlib import Path
from azure.storage.blob import BlobServiceClient

conn = Path(".secrets/azure_connection_string").read_text().strip()
svc  = BlobServiceClient.from_connection_string(conn)
cli  = svc.get_container_client("anti-bad")
blob = cli.get_blob_client("smoke/hello.txt")
blob.upload_blob(b"hello from laptop", overwrite=True)
print("uploaded. listing:")
for b in cli.list_blobs(name_starts_with="smoke/"):
    print(" ", b.name, b.size, "bytes")
```

Run it (PowerShell on Vetle's laptop):

```powershell
conda activate bachelorenv
python dashboard\smoke_test.py        # minimal upload/list
python dashboard\smoke_e2e.py         # 7-stage round-trip
```

> The smoke-test scripts used to live under `scripts/azure/` but were moved
> to `dashboard/` in the 2026-04 consolidation so every Azure-facing piece
> of Python sits next to `dashboard/server.py` and `dashboard/azure_io.py`.

Expected output:
```
uploaded. listing:
  smoke/hello.txt 17 bytes
```

### HPC — upload with AzCopy

```bash
ssh vetle@10.10.15.10
cd ~/bachelor-anti-bad
CONN=$(cat .secrets/azure_connection_string)
ACCOUNT=$(echo "$CONN" | sed -E 's/.*AccountName=([^;]+).*/\1/')
KEY=$(echo "$CONN" | sed -E 's/.*AccountKey=([^;]+).*/\1/')

echo "hello from hpc" > /tmp/hpc_smoke.txt

# Build a short-lived SAS on the fly from the account key for azcopy.
# (For now the simplest path is: use azcopy login OR a SAS token in the URL.)
# Easiest: generate a SAS in the portal for the container and export it:
export AZCOPY_SAS='PASTE_CONTAINER_SAS_HERE'
azcopy copy /tmp/hpc_smoke.txt "https://${ACCOUNT}.blob.core.windows.net/anti-bad/smoke/hpc.txt?${AZCOPY_SAS}"
```

> AzCopy doesn't accept a raw connection string — it needs either `azcopy
> login` (AAD) or a SAS token appended to the URL. We'll generate a
> container-scoped SAS token in Step 9.

## Step 9 — Generate a SAS Token for AzCopy (HPC only)

1. Storage account → **Security + networking** → **Shared access signature**.
2. Allowed services: **Blob**.
3. Allowed resource types: **Service, Container, Object**.
4. Allowed permissions: **Read, Write, List, Create, Add**. (No Delete — safer.)
5. Start: now. End: pick a date after your thesis defence (e.g. 2027-06-30).
6. Allowed protocols: **HTTPS only**.
7. Signing key: `key1`.
8. **Generate SAS and connection string**.
9. Copy the **SAS token** (the `?sv=...` string). Save on HPC at
   `~/bachelor-anti-bad/.secrets/azure_sas_token`, `chmod 600`.

## Step 10 — Share with your group (4 collaborators)

The storage account is yours, but all 4 thesis members will upload into the
same container from their own HPC accounts.

1. **Credential to share**: the **container SAS token** from Step 9 (NOT the
   connection string — that grants account-level admin). The SAS is scoped to
   the `anti-bad` container with read/write/list/create but no delete.
2. Share the SAS out-of-band (Signal, 1Password, encrypted email) — never
   over a public channel and never in git.
3. Each member does the following on **both** their HPC and their laptop:
   ```bash
   cd ~/bachelor-anti-bad
   mkdir -p .secrets
   printf '%s' 'PASTE_SAS_TOKEN_HERE' > .secrets/azure_sas_token
   chmod 600 .secrets/azure_sas_token
   ```
4. Each member exports their identifier. Add to `~/.bashrc` on HPC and to
   their laptop shell profile:
   ```bash
   export MEMBER=vetle    # or alice, bob, carol — must be unique per person
   ```
5. From Phase 2 onward, the SLURM scripts and `server.py` use `${MEMBER}` as
   the top-level blob prefix, so everyone's files stay separated.

**If a member leaves the group**: generate a fresh SAS in the portal
(Shared access signature → set start date = now, revoking the old one) and
redistribute. The old token stops working immediately.

**Dashboard view**: once Phase 2 is done, the dashboard will list all members'
results side-by-side, with a filter for "show only my results" when you're
debugging your own runs.

## Checklist before coming back

- [ ] Pay-As-You-Go subscription active
- [ ] `thesis-hard-cap` $10/month budget + 50/80/100% alerts set up
- [ ] Resource group `bachelor-anti-bad` in Norway East
- [ ] Storage account created in Norway East (write its name here: _________________)
- [ ] Container `anti-bad` created (private)
- [ ] `.secrets/azure_connection_string` on laptop (chmod 600)
- [ ] `.secrets/azure_connection_string` on HPC (chmod 600)
- [ ] `.secrets/azure_sas_token` on HPC (chmod 600)
- [ ] `MEMBER=<yourname>` exported in HPC `~/.bashrc` and laptop shell
- [ ] Python smoke test uploaded `smoke/hello.txt` successfully
- [ ] AzCopy installed on HPC, version printed
- [ ] Group members have the SAS token + their own MEMBER env var set

Once those are all ticked, we'll move to Phase 2:

1. Add `dashboard/azure_io.py` — shared blob I/O helpers.
2. Modify `dashboard/server.py` to read logs/results/data from Azure instead of
   `PROJECT_ROOT` subpaths.
3. Update `dashboard/index.html` sync controls (remove "SCP sync", replace with
   "Refresh from Azure").
4. Extend `scripts/slurm/textattack.slurm` (and siblings) with a trailing
   `azcopy sync` step pushing the job's log + results up to the container.
5. Update `requirements.txt` and `environment.yml` with `azure-storage-blob`.

Ping me when you've got the storage account name + smoke test passing, and
I'll do the code conversion.
