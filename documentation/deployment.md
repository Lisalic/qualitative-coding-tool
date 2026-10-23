# Deployment

The backend runs on one Oracle Cloud **Always Free** VM as a Docker Compose stack ([deploy/docker-compose.yml](../deploy/docker-compose.yml)):

| Service | What it is |
|---|---|
| `db` | Postgres 16, data in the `pgdata` volume |
| `api` | The FastAPI app, built from the root [Dockerfile](../Dockerfile); runs Alembic migrations on startup |
| `caddy` | HTTPS on ports 80/443, with an automatic Let's Encrypt certificate for `API_DOMAIN`, proxying to `api` |

The frontend stays on Vercel and calls the API at `https://<API_DOMAIN>` through `VITE_API_URL`.

On every push to `main`, [.github/workflows/main.yml](../.github/workflows/main.yml) runs the backend and frontend test suites. If they pass, it rsyncs `Dockerfile`, `alembic.ini`, `backend/` and `deploy/` to the VM over SSH, runs `docker compose up -d --build`, and waits for the API to answer. The deploy job is skipped until the `DEPLOY_HOST` repository variable is set.

The API runs **one uvicorn worker on purpose**: background jobs are in-process asyncio tasks (see [architecture.md](architecture.md#background-jobs)), so a second worker could not see or cancel the first one's jobs.

## One-time setup

### 1. Create the VM

In the Oracle Cloud console, open **Compute → Instances → Create instance**:

- Image: **Canonical Ubuntu 24.04**.
- Shape: **Ampere → VM.Standard.A1.Flex**, for example 2 OCPU and 12 GB. The Always Free limit is 4 OCPU and 24 GB in total.
- Boot volume: choose **Specify a custom boot volume size** and set it to **200 GB**. The default of about 47 GB holds far less data, and 200 GB is the free limit.
- Add your SSH public key, and keep **Assign a public IPv4 address** on.

If you get "Out of capacity", try a different availability domain or try again later.

### 2. Open ports 80 and 443 in Oracle's network

In the console, open the instance's subnet, then **Security List**, then **Add Ingress Rules**: source `0.0.0.0/0`, TCP, destination ports `80,443`.

### 3. Bootstrap the VM

From the repository root, run [deploy/bootstrap.sh](../deploy/bootstrap.sh) on the VM:

```bash
ssh ubuntu@<VM_IP> 'bash -s' < deploy/bootstrap.sh
```

The script does three things:
- Opens ports 80 and 443 in the VM's own firewall. Oracle's Ubuntu image rejects everything except SSH.
- Installs Docker.
- Writes `~/qualitative-coding/deploy/.env` with freshly generated secrets, and sets `API_DOMAIN` to `<ip-with-dashes>.sslip.io`. To use a real domain instead, edit `API_DOMAIN` in that file; [deploy/.env.example](../deploy/.env.example) lists every setting.

Deploys never touch `deploy/.env`. The script is safe to run again.

### 4. First deploy by hand (optional)

To get the API up before setting up GitHub Actions, run the same two steps the deploy job runs, from the repository root:

```bash
rsync -az --delete --exclude='deploy/.env' --exclude='__pycache__/' Dockerfile .dockerignore alembic.ini backend deploy ubuntu@<VM_IP>:qualitative-coding/
```

```bash
ssh ubuntu@<VM_IP> 'cd qualitative-coding/deploy && docker compose up -d --build'
```

### 5. Give GitHub Actions a deploy key

On your own machine, create a key that is used only for deploys, and authorize it on the VM:

```bash
ssh-keygen -t ed25519 -f ~/.ssh/qct_deploy -N "" -C github-deploy
```

```bash
ssh-copy-id -i ~/.ssh/qct_deploy.pub ubuntu@<VM_IP>
```

Then, in the GitHub repository, open **Settings → Secrets and variables → Actions**:

| Kind | Name | Value |
|---|---|---|
| Secret | `DEPLOY_SSH_KEY` | contents of `~/.ssh/qct_deploy` (the private key) |
| Secret | `DEPLOY_KNOWN_HOSTS` | output of `ssh-keyscan -t ed25519 <VM_IP>`, run after you've connected once and accepted the key |
| Variable | `DEPLOY_HOST` | the VM's public IP |
| Variable | `DEPLOY_USER` | optional; defaults to `ubuntu` |

### 6. Deploy

Push to `main`, or run the workflow by hand:

```bash
gh workflow run main.yml
```

The first build on the VM takes a few minutes. Afterwards, `https://<API_DOMAIN>/` should return `{"message": "Qualitative Coding API"}`.

### 7. Point the frontend at it

In Vercel, set `VITE_API_URL=https://<API_DOMAIN>` and redeploy the frontend. CORS in [backend/app/main.py](../backend/app/main.py) already allows the Vercel origins.

## Operating it

Run these on the VM, from `~/qualitative-coding/deploy`.

Follow the API logs:

```bash
docker compose logs -f api
```

Restart the API:

```bash
docker compose restart api
```

Back up the database:

```bash
docker compose exec -T db pg_dump -U qct qct | gzip > ~/qct-$(date +%F).sql.gz
```

Open a Postgres shell:

```bash
docker compose exec db psql -U qct qct
```

Restarting `api` fails any AI job in flight. This is the same trade-off as any restart, described in [architecture.md](architecture.md#background-jobs).
