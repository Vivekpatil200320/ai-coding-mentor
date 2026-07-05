# ADR-0006: Deployment target must expose Docker socket access — rules out most serverless/PaaS hosts

- **Status:** Accepted
- **Date:** 2026-07-05
- **Deciders:** Backend

## Context

`backend/sandbox/docker_runner.py` executes untrusted student code by
spawning sibling containers via `docker.from_env()` (docker-py talking to
the Docker daemon's Unix socket). This is the "Docker-outside-of-Docker"
(DooD) pattern: the backend process needs the *same* daemon that will run
the sandbox containers, not an isolated/nested one. `docker-compose.prod.yml`
mounts `/var/run/docker.sock` into the backend container to make this work.

This has a real consequence for where the app can be deployed, and it was
worth writing down before someone picks a host and discovers the constraint
mid-deploy.

## Decision

Document (not yet act on) that this architecture requires a deployment
target with genuine Docker daemon access:

- **Works:** a VM/droplet/EC2 instance running Docker (Compose or otherwise),
  a Docker-enabled CI runner repurposed as a host, Fly.io Machines with a
  Docker-capable image, or a Kubernetes node with a DinD sidecar or
  privileged pod.
- **Does not work out of the box:** Vercel, most classic PaaS (Render's/
  Railway's standard web service tier, Heroku), or any "serverless function"
  target — none of these expose a Docker socket to application code, and
  several explicitly forbid privileged container operations.

`docker-compose.prod.yml` targets the "works" case (a Docker-capable host)
directly.

## Consequences

- **Positive:** no architecture change needed — the sandbox design (real
  container isolation for untrusted code, verified via the hardening audit)
  is worth keeping over a lighter-weight alternative.
- **Negative:** narrows hosting choice before any hosting decision has been
  made. Whoever deploys this needs to pick (or already have) a VM-shaped
  target, not just the cheapest PaaS tier.
- **Negative:** the backend container effectively has root-adjacent power
  over the host (Docker socket access is equivalent to root on most hosts).
  This is an accepted risk of the DooD pattern — the sandbox's own hardening
  (network-disabled, resource-limited, non-root, cap-dropped containers, see
  `docs/security/sandbox-audit.md`) protects against a malicious *student
  submission*, but it does not protect against a compromised *backend
  process* reaching for the socket directly. That threat model (backend RCE)
  is out of scope for this pass.

## Alternatives considered

- **Rootless Docker / gVisor / Kata Containers** for stronger isolation
  between the backend and the host. Real improvement, meaningfully more
  operational complexity, deferred until there's an actual deployment to
  harden rather than speccing it in the abstract.
- **Sandbox-as-a-service (e.g. a managed code-execution API)** instead of
  self-hosted Docker. Would remove the hosting constraint entirely, but
  reintroduces the zero-budget problem this project is built around (ADR-0004)
  — free tiers of managed sandboxes are far more limited than free-tier LLM
  calls. Revisit if the zero-budget constraint is lifted.
