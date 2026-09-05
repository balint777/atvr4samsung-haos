# Changelog

## 0.5.0

- Close an automatically opened pairing window after its first successful
  enrollment; manually opened windows remain reusable until expiry.
- Automatically dismiss the Home Assistant pairing notification when pairing
  succeeds, the window expires, it is cancelled, or the app finds a stale
  notification after restarting.

## 0.4.0

- Detect an unpaired iPhone's Pair-Setup request, continue the same connection,
  and automatically create a Home Assistant notification with its PIN.
- Present the PIN prominently with numbered iPhone steps and a human-readable
  relative expiry instead of a raw timestamp.
- Disable startup-time automatic pairing by default now that client-triggered
  pairing is available; the input action and one-shot request remain fallbacks.

## 0.3.0

- Accept a `{"command":"pair"}` Home Assistant app-input action without
  restarting the bridge.
- Create a persistent Home Assistant notification containing the temporary
  pairing PIN and expiry, while retaining the log output as a fallback.

## 0.2.0

- Open a temporary pairing window automatically at startup while no iPhone is
  paired, with an opt-out for installations that require explicit enrollment.
- Keep automatic enrollment closed if paired-phone state cannot be inspected.

## 0.1.6

- Acknowledge the `FetchCurrentTopShelfItemsEvent` request added to the iOS 27
  TV Remote session startup, returning an empty successful result instead of an
  unsupported-handler error.

## 0.1.5

- Accept the Apple Watch's empty cleartext `NoOp` idle keepalive without
  attempting AEAD decryption or consuming the inbound nonce counter.

## 0.1.4

- Relay the watchOS HID release value (`_hBtS=0`), including release-only
  Play/Pause events, while retaining the iOS press/release values.
- Relay legacy `_mcc` Crown volume and media commands to Samsung.
- Add content-free Companion identifier, frame type, and inbound-counter
  diagnostics for any remaining watchOS disconnects.

## 0.1.3

- Added per-connection negotiation for the different implicit ChaCha20-Poly1305
  nonce layouts used by Companion clients.
- Accept identifier-less Companion response frames from Apple Watch without
  counting them as malformed commands.

## 0.1.2

- Added the current iOS movement phase (`_tPh=2`) to the gesture mapping and
  bypassed upstream's unused last-touch bookkeeping decoder, which rejects that
  phase and closes the connection after three movements.
- Added the HAOS app version to every startup log for deployment verification.

## 0.1.1

- Fixed iPhone trackpad gestures disconnecting after three touch frames when
  iOS omits the optional `_ns` touch timestamp.
- Added a source-hash guard and a container-level regression check for the
  compatibility patch.

## 0.1.0

- Initial HAOS wrapper for upstream `atvr4samsung` 2.0.1.
- Added Supervisor configuration translation, persistent state preparation,
  explicit Samsung TLS fingerprint approval, one-shot iPhone pairing requests,
  one-shot identity reset, privilege dropping, and signal forwarding.
