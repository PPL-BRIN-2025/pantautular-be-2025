## Security Posture

This project aligns with the [OWASP Top 10](https://owasp.org/www-project-top-ten/) and the [OWASP CSV Injection Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/CSV_Injection_Prevention_Cheat_Sheet.html) to keep API and data exports resilient against common attack classes.

### Implemented Controls
- **Broken Access Control (OWASP A01)** – Expert case mutation endpoints now verify that the authenticated expert owns the record (via `created_by` or their upload batch) before allowing updates/deletions, preventing horizontal privilege escalation.
- **Injection Hardening (OWASP A03)** – All values mirrored into expert datasets are scrubbed for control characters and prefixed when they resemble spreadsheet formulas, eliminating CSV/Formula injection vectors when analysts download data.
- **Defense in Depth** – Existing Django security middleware, CSP, HTTP security headers, JWT auth, throttling, Prometheus auditing, and download logging remain enabled so controls span validation, transport, and monitoring layers.
- **Testing & Monitoring** – The new protections ship with regression tests to prevent regressions, and violations are logged via existing audit hooks for anomaly detection.

### SDLC & Supply-Chain Considerations
- **Signed Artifacts & Commits** – Enforce GPG-signed commits/tags for release branches so provenance is verifiable before deployments; document the trusted keys list in the release playbook.
- **Dependency Hygiene** – Lock dependencies, enable Dependabot/Snyk alerts, and run `pip-audit` (or equivalent) during CI to flag vulnerable packages early in the lifecycle.
- **Secrets & Configuration** – Keep `.env` secrets rotated, injected via the deployment platform, and never committed. Prefer secret-scanning hooks (e.g., `git-secrets`) for pre-commit enforcement.
- **Secure Build/Test** – Run the Django/pytest suites plus SAST (Bandit), container scans, and coverage gates in CI; fail builds below 100 % coverage or when security tests fail.
- **Operational Monitoring** – Maintain Sentry/Prometheus alerts for anomalous authentication failures or unexpected dataset downloads to catch abuse quickly.

Following these practices keeps security expectations visible to every contributor throughout the SDLC while grounding the implementation in OWASP guidance.
