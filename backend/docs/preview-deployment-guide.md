# Preview Deployment Next to Production

This guide explains how to run a preview deployment alongside production using the same Docker environment. It relies on environment variables supplied via a `.env` file so the compose stack never falls back to baked-in network names.

## 1. Prerequisites
- Docker and Docker Compose installed.
- Access to the production `docker-compose.coolify.yaml` file in this repository.
- A `.env` file that defines network names, Traefik configuration, database credentials, and Django secrets for each deployment.

## 2. Define environment variables
Create two `.env` files—one for production and one for preview. The key requirement is that network names come from the `.env` file (no defaults in the compose file).

Example `production.env`:
```
DOCKER_NETWORK=api-security-internal
TRAEFIK_NETWORK=api-security-proxy
TRAEFIK_NETWORK_EXTERNAL=true
TRAEFIK_ROUTER_NAME=api_security
TRAEFIK_SERVICE_NAME=api_security
SERVICE_FQDN_WEB=api.security.ait.dtu.dk
SERVICE_URL_WEB=https://api.security.ait.dtu.dk
DJANGO_SECRET=...prod-secret...
POSTGRES_PASSWORD=...prod-password...
```

Example `preview.env` (use unique hostnames and router names):
```
DOCKER_NETWORK=api-security-internal
TRAEFIK_NETWORK=api-security-proxy
TRAEFIK_NETWORK_EXTERNAL=true
TRAEFIK_ROUTER_NAME=api_security_preview
TRAEFIK_SERVICE_NAME=api_security_preview
SERVICE_FQDN_WEB=preview.api.security.ait.dtu.dk
SERVICE_URL_WEB=https://preview.api.security.ait.dtu.dk
DJANGO_ALLOWED_HOSTS=preview.api.security.ait.dtu.dk
DJANGO_CSRF_TRUSTED_ORIGINS=https://preview.api.security.ait.dtu.dk
AZURE_REDIRECT_URI=https://preview.api.security.ait.dtu.dk/auth/callback
DJANGO_SECRET=...preview-secret...
POSTGRES_PASSWORD=...preview-password...
POSTGRES_DB=app_preview
POSTGRES_USER=app_preview
CACHE_URL=redis://redis:6379/1
```

> The shared network names allow both stacks to communicate with the Traefik proxy, while distinct router/service names and hostnames keep routing separate.

## 3. Start production
From the `backend` directory, run:
```
cp production.env .env
docker compose -f docker-compose.coolify.yaml up -d
```

## 4. Start preview alongside production
Use the preview environment file without stopping production:
```
cp preview.env .env
docker compose -p api-security-preview -f docker-compose.coolify.yaml up -d
```

Notes:
- The `-p` flag assigns a unique project name so containers do not clash with the production ones.
- Ensure the preview database credentials point to a separate database/schema to avoid data overlap.

## 5. Traefik routing
Traefik uses values from `.env`:
- `TRAEFIK_NETWORK` must match the external proxy network name.
- `TRAEFIK_ROUTER_NAME` and `TRAEFIK_SERVICE_NAME` must be unique per deployment (production vs. preview).
- `SERVICE_FQDN_WEB` sets the hostname rule; ensure DNS points the preview hostname to the proxy.

## 6. Verifying both stacks
- Access production at `https://api.security.ait.dtu.dk`.
- Access preview at `https://preview.api.security.ait.dtu.dk`.

Use `docker compose ls` to confirm both projects are running and `docker compose logs -f` (with the correct `-p` value) to inspect each stack.
