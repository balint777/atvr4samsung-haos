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
lifecycle process and configuration translation on top of that image. Releases
0.1.2 through 0.1.6 also apply narrow compatibility patches for current-iOS
touch frames, Apple Watch encryption and input variants, the Watch idle
keepalive, and the iOS 27 Top Shelf startup request. Each build patch verifies
the exact input source against a pinned SHA-256 digest and fails closed if the
installed upstream source differs. Container-level regression checks run
immediately after every patch.
