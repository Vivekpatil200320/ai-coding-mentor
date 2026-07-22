# Security Policy

ai-coding-mentor executes untrusted, LLM-generated student code inside a Docker sandbox (`sandbox/`) as part of its grading loop, and separately calls out to LLM providers (NVIDIA NIM) and Supabase for persistence.

## Threat model

Two distinct risks apply to the sandboxed execution path:

1. **Classic container escape** — network access, resource limits, and Linux capabilities available to the executed code.
2. **Prompt injection via sandbox output** — a student's code can shape its own `stdout`/`stderr` to try to manipulate the LLM that later reads that output for grading.

The full audit — what's fixed, what's mitigated-not-closed, and why — is documented in [`docs/security/sandbox-audit.md`](docs/security/sandbox-audit.md); the architectural reasoning behind the sandbox and its boundaries is captured in [`docs/adr/`](docs/adr/).

## Scope

- Sandbox escape or privilege escalation from executed student code
- Prompt injection that bypasses the grading rubric's intended behavior
- Authorization bypass in the Supabase RLS / service-role design (see the relevant ADR)
- Secrets or API keys leaking into logs, responses, or the sandbox environment

## Reporting

This is a personal/portfolio project. If you find an issue, please open a GitHub issue on this repo, or contact me directly via the email in my GitHub profile for anything you'd rather not disclose publicly first.
