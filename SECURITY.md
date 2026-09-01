# Security notes

- The app uses host networking because Apple Companion discovery requires mDNS
  multicast and TV wake-up requires Wake-on-LAN. It therefore has less network
  isolation than a normal HAOS app.
- No Supervisor or Home Assistant API permission, privileged capability,
  Docker socket, or Home Assistant configuration mount is requested.
- The bridge process drops from root to UID/GID 65532 before it contacts the TV
  or accepts iPhone connections.
- Persistent identity, phone pairings, Samsung access token, and Samsung TLS
  certificate pin are stored under the app's private `/data/state` directory.
- The Samsung WebSocket uses TLS port 8002 and starts only after the operator
  approves the exact live certificate SHA-256 fingerprint.
- A pairing window is closed by default. It opens only when a new one-shot
  `pairing_request` value is submitted.

Report vulnerabilities in the HAOS wrapper to the repository maintainer. For
issues in the Companion or Samsung implementation, follow the upstream
project's [security policy](https://github.com/vb3/atvr4samsung/security/policy).

