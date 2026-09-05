# Pinned upstream release

The app image derives from the following immutable upstream release:

- Project: [`balint777/atvr4samsung`](https://github.com/balint777/atvr4samsung)
- Release: `2.1.2`
- Source commit: `565f70fac31d1a51ec4ce0a768dc3721ae6d8958`
- Multi-architecture image:
  `ghcr.io/balint777/atvr4samsung@sha256:b1c636fe1ba971513fdf021ff194cd655932b08681b83bd4b6a07d931b365abf`

Those values come from upstream's release metadata asset
`atvr4samsung-2.1.2-release.env`. Upstream publishes that metadata and the
deployment bundle with GitHub artifact attestations. The wrapper adds its HAOS
lifecycle process and configuration translation on top of that image. Releases
0.1.2 through 0.4.0 also apply narrow compatibility patches for current-iOS
touch frames, Apple Watch encryption and input variants, the Watch idle
keepalive, and the iOS 27 Top Shelf startup request. Each build patch verifies
the exact input source against a pinned SHA-256 digest and fails closed if the
installed upstream source differs. Container-level regression checks run
immediately after every patch.
