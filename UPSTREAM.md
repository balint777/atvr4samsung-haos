# Pinned upstream release

The app image derives from the following immutable upstream release:

- Project: [`vb3/atvr4samsung`](https://github.com/vb3/atvr4samsung)
- Release: `2.0.1`
- Source commit: `805c5722056c5adf52d497f5c48b7e80ae77ea27`
- Multi-architecture image:
  `ghcr.io/vb3/atvr4samsung@sha256:169d7766eaa0eb4de69cbd90d1aff65554bac782d1ac8902ed95ecd5d3824d6d`

Those values come from upstream's release metadata asset
`atvr4samsung-2.0.1-release.env`. Upstream publishes that metadata and the
deployment bundle with GitHub artifact attestations. The wrapper adds its HAOS
lifecycle process and configuration translation on top of that image. Version
0.1.2 also applies one audited compatibility patch: it bypasses upstream's
unused last-touch bookkeeping decoder, maps the captured current-iOS movement
phase (`_tPh=2`), and validates only the touch fields used by the relay. This
tolerates optional fields and differing scalar representations without
weakening Companion framing or authorization. The build verifies upstream
`companion/server.py` against
SHA-256
`8e6f4bc55a8123a0bdf82e56dc3bd082ffb31f217dd0fce390c7e7098bfbcc4f`
before changing that handler, and fails closed if the source differs.
