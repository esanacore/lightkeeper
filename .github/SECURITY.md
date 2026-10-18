# Project Security

This project follows [Eric's Engineering Constitution Security Standards](../constitution/SECURITY.md). It handles glucose data, which is health data and classified **Restricted**. The data classification, retention rules, and threat model are in [`docs/SECURITY_MODEL.md`](../docs/SECURITY_MODEL.md); the safety boundary and hazard log are in [`docs/SAFETY.md`](../docs/SAFETY.md).

## Reporting a Vulnerability

Please report security issues privately, not in a public issue. Use GitHub's **Report a vulnerability** button on this repository's Security tab (private vulnerability reporting), or email the maintainer at esanacore@gmail.com with "Lightkeeper security" in the subject. Expect an acknowledgment within 7 days.

Anything that could change what number or status a display shows is treated as a safety issue as well as a security issue, and gets a hazard review in `docs/SAFETY.md`.

## Local Security Concerns

- **LAN Exposure**: Lightkeeper opens no ports and runs no server. It only makes outbound HTTPS GET requests to the configured Nightscout site. The `--svg` option writes a local file; serving that file to a dashboard is the deployer's choice and should stay on the LAN.
- **Credential Handling**: Never commit secrets. The only credential is a Nightscout token with the **readable** role, set in the environment (`NIGHTSCOUT_TOKEN`) or an ignored `.env` file. Never use the Nightscout API_SECRET with Lightkeeper. The token is redacted from every error message.
- **Sensitive Data**: Glucose readings and their timestamps are personal health data. Lightkeeper keeps only the most recent reading in memory, writes nothing to disk except the optional `--svg` screen image, and never logs readings beyond what it prints to the screen it drives.

## Security Checklist

- [x] Credentials are stored in environment variables, not code.
- [x] Dependencies are audited for vulnerabilities (no runtime dependencies; dev tools tracked in `docs/OTS_SOFTWARE.md` and updated by Dependabot).
- [x] Inputs are validated at boundaries (strict Nightscout entry parsing, HTTPS-only URLs, validated thresholds).
- [x] Logs do not contain secrets or PII beyond the display output itself.
- [x] A threat model was produced for the Nightscout egress path (`docs/SECURITY_MODEL.md`), per the constitution's [Threat Modeling Triggers](../constitution/SECURITY.md).
