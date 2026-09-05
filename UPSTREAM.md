# Pinned upstream release

The app image derives from the following immutable upstream release:

- Project: [`balint777/atvr4samsung`](https://github.com/balint777/atvr4samsung)
- Release: `2.2.0`
- Source commit: `e156ecbbf7db5ee90c33b0695d462e8089db82ee`
- Multi-architecture image:
  `ghcr.io/balint777/atvr4samsung@sha256:4805adf802ae2cab92e16dee36df7eb6adf4cb2052e9352c921d67170cd3f5ba`

Those values come from upstream's release metadata asset
`atvr4samsung-2.2.0-release.env`. Upstream publishes that metadata and the
deployment bundle with GitHub artifact attestations. The wrapper adds its HAOS
lifecycle process and configuration translation on top of that image. Releases
0.1.2 through 0.6.0 also apply narrow compatibility patches for current-iOS
touch frames, Apple Watch encryption and input variants, the Watch idle
keepalive, and the iOS 27 Top Shelf startup request. Each build patch verifies
the exact input source against a pinned SHA-256 digest and fails closed if the
installed upstream source differs. Container-level regression checks run
immediately after every patch.
