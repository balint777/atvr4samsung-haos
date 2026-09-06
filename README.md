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
an explicit Samsung TLS-certificate fingerprint. Selecting the remote from an
unpaired iPhone then opens pairing on demand and publishes its temporary PIN in
Home Assistant.

## Scope

The wrapper is intentionally thin. It:

- pins upstream `atvr4samsung` 2.2.0 by its signed multi-architecture OCI digest;
- translates Supervisor options into the upstream YAML configuration;
- keeps identity, phone pairings, the Samsung token, and TLS pin in app data;
- runs the bridge as unprivileged UID/GID 65532;
- detects an unpaired iPhone's setup request and publishes its temporary PIN
  as a Home Assistant notification;
- closes an on-demand window after the first successful enrollment and removes
  the notification on completion or expiry;
- retains a Home Assistant input action for manually opening pairing;
- optionally advertises a separate, power-only HomeKit Television backed by an
  existing Home Assistant `media_player`, without HomeKit remote keys;
- automatically chooses and remembers an available port for that HomeKit
  accessory, with an optional fixed-port override;
- retains one-shot request fields for pairing and Apple-side identity resets.

The upstream project currently describes Samsung Frame TVs as its tested
target. Other modern Tizen TVs may work through the same WebSocket API but are
not guaranteed by this wrapper.

## Upgrading upstream

Upstream images are never consumed through a moving tag. To upgrade, verify a
new upstream release and its signed `atvr4samsung-X.Y.Z-release.env`, update the
digest in `atvr4samsung/Dockerfile`, then bump the wrapper version and changelog.

See [UPSTREAM.md](UPSTREAM.md) for the currently pinned release.
