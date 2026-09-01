# Changelog

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
