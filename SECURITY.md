# Security notes

- The app uses host networking because Apple Companion discovery requires mDNS
  multicast and TV wake-up requires Wake-on-LAN. It therefore has less network
  isolation than a normal HAOS app.
- Home Assistant Core API access is used only to create the pairing-PIN
  notification. The app has no Supervisor management API permission,
  privileged capability, Docker socket, or Home Assistant configuration mount.
- The bridge process drops from root to UID/GID 65532 before it contacts the TV
  or accepts iPhone connections.
- Persistent identity, phone pairings, Samsung access token, and Samsung TLS
  certificate pin are stored under the app's private `/data/state` directory.
- The Samsung WebSocket uses TLS port 8002 and starts only after the operator
  approves the exact live certificate SHA-256 fingerprint.
- A short pairing window opens automatically while no phone is paired, unless
  disabled. Later windows require either a new one-shot `pairing_request` or
  the explicit Home Assistant `pair` input action.
- The Supervisor bearer token is read only from the environment, sent only to
  the internal Home Assistant Core proxy, and never written to logs or state.

Report vulnerabilities in the HAOS wrapper to the repository maintainer. For
issues in the Companion or Samsung implementation, follow the upstream
project's [security policy](https://github.com/vb3/atvr4samsung/security/policy).
