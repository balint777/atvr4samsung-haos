# atvr4samsung for Home Assistant OS

This repository packages
[`vb3/atvr4samsung`](https://github.com/vb3/atvr4samsung) as a Home Assistant
OS app (formerly called an add-on).

It makes the host advertise an Apple TV Companion Link endpoint. The native
iPhone Control Center Remote and Apple Watch Remote pair with that endpoint,
and commands are sent to a Samsung Tizen television over its local TLS
WebSocket API.

## Install from GitHub

1. Publish this directory as a GitHub repository.
2. In Home Assistant, open **Settings → Apps → App store → Repositories**.
3. Add the GitHub repository URL.
4. Install **atvr4samsung Companion Bridge**.

For a local test, copy the `atvr4samsung/` directory to `/addons/atvr4samsung`
on HAOS and reload the app store.

Read the app's **Documentation** tab before starting it. Initial setup requires
an explicit Samsung TLS-certificate fingerprint and a one-shot pairing request.

## Scope

The wrapper is intentionally thin. It:

- pins upstream `atvr4samsung` 2.0.1 by its signed multi-architecture OCI digest;
- translates Supervisor options into the upstream YAML configuration;
- keeps identity, phone pairings, the Samsung token, and TLS pin in app data;
- runs the bridge as unprivileged UID/GID 65532;
- exposes one-shot request fields for opening an iPhone pairing window or
  resetting the emulated Apple TV identity.

The upstream project currently describes Samsung Frame TVs as its tested
target. Other modern Tizen TVs may work through the same WebSocket API but are
not guaranteed by this wrapper.

## Upgrading upstream

Upstream images are never consumed through a moving tag. To upgrade, verify a
new upstream release and its signed `atvr4samsung-X.Y.Z-release.env`, update the
digest in `atvr4samsung/Dockerfile`, then bump the wrapper version and changelog.

See [UPSTREAM.md](UPSTREAM.md) for the currently pinned release.
