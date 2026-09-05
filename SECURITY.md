# Security notes

- The app uses host networking because Apple Companion discovery requires mDNS
  multicast and TV wake-up requires Wake-on-LAN. It therefore has less network
  isolation than a normal HAOS app.
- Home Assistant Core API access creates and dismisses pairing notifications.
  When the optional minimal HomeKit Television is enabled, it also reads one
  explicitly configured `media_player` state and calls only its standard
  `turn_on` and `turn_off` services. The app has no Supervisor management API
  permission, privileged capability, Docker socket, or Home Assistant
  configuration mount.
- The bridge process drops from root to UID/GID 65532 before it contacts the TV
  or accepts iPhone connections.
- Persistent Companion and optional HomeKit identities, pairing records,
  Samsung access token, and Samsung TLS certificate pin are stored under the
  app's private `/data/state` directory.
- The Samsung WebSocket uses TLS port 8002 and starts only after the operator
  approves the exact live certificate SHA-256 fingerprint.
- With `pair_on_demand` enabled, an admitted LAN Pair-Setup request opens one
  short identity-bound window. Repeated requests reuse it, existing attempt
  throttles still apply, and enrollment still requires the PIN delivered to
  Home Assistant. The first successful enrollment consumes an on-demand window;
  an operator-opened window remains reusable until expiry. The explicit input
  action remains available as a fallback.
- The Supervisor bearer token is read only from the environment, sent only to
  the internal Home Assistant Core proxy, and never written to logs or state.

Report vulnerabilities in the HAOS wrapper to the repository maintainer. For
issues in the Companion or Samsung implementation, follow the upstream
project's [security policy](https://github.com/vb3/atvr4samsung/security/policy).
