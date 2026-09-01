# Setup

This app wraps upstream `atvr4samsung` 2.0.1. It advertises an Apple TV-like
Companion Link service on the HAOS host and sends commands directly to the
Samsung TV. Home Assistant automations and the HomeKit Bridge are not involved
in this path.

## 1. Prepare the network and television

- Reserve the TV's IP address in DHCP.
- Find the TV's wired or wireless MAC address. Use the MAC belonging to the
  interface the TV actually uses.
- Keep the TV, HAOS host and iPhone on the same multicast domain. If the phone
  is on another VLAN, reflect `_companion-link._tcp` mDNS records between the
  VLANs and allow the configured Companion TCP port.
- Turn the television on for initial TLS trust and Samsung remote approval.

The app uses host networking for mDNS and Wake-on-LAN. It does not request the
Docker socket, privileged capabilities, the Supervisor API, or access to Home
Assistant's configuration.

## 2. Enter the base configuration

Set at least:

- `device_name`: name shown in the iPhone Remote target picker.
- `samsung_host`: reserved TV IPv4 address or LAN hostname.
- `samsung_mac`: TV MAC address in `AA:BB:CC:DD:EE:FF` form.
- `wol_broadcast`: directed subnet broadcast such as `192.168.1.255`. The
  limited broadcast `255.255.255.255` is the default but does not work on every
  network.

Keep Samsung port 8002: upstream deliberately rejects plaintext port 8001.
The Companion port defaults to 49152 and must not already be in use on HAOS.

Leave `samsung_tls_fingerprint` empty for the first start.

## 3. Approve the Samsung TLS certificate

Start the app while the TV is awake. It performs a token-free TLS handshake,
prints a line like this, and stops without starting the remote service:

```text
Fetched Samsung TLS certificate SHA-256: <64 hexadecimal characters>
```

Verify that fingerprint independently when practical. From another trusted
computer with OpenSSL, replace `TV_IP` below:

```bash
openssl s_client -connect TV_IP:8002 -showcerts </dev/null 2>/dev/null \
  | openssl x509 -outform DER \
  | openssl dgst -sha256
```

Paste the 64-character fingerprint into `samsung_tls_fingerprint` and start the
app again. The wrapper refetches the live certificate and persists it only when
the supplied fingerprint matches exactly. Later starts reuse the private pin;
they do not silently trust a changed certificate.

## 4. Pair the iPhone

`pairing_request` is a one-shot request token, not the four-digit PIN. Enter any
new label, for example `first-phone-2026-08-31`, save the configuration and
restart the app. After the bridge becomes ready, the logs show a temporary
four-digit PIN and its expiry.

On the iPhone:

1. Open **Control Center → Remote**.
2. Select the configured `device_name`.
3. Enter the PIN shown in the app log before it expires.

The same `pairing_request` value is processed only once, including after later
restarts. To add another phone or request another PIN, replace it with a new
value. Pairing is closed at all other times.

On the first actual command, Samsung should display an **Allow remote device**
prompt for `samsung_remote_name`. Approve it with the physical remote. The
resulting token persists in the app's private data.

## 5. Reset all Apple-side pairing

If the iPhone retains a broken pairing or you need to revoke every paired
phone, put a new unique value in `reset_identity_request` and restart the app.
This deletes the emulated Apple TV identity and all paired-phone authorization,
but preserves the Samsung token and TLS pin. The operation is one-shot per
unique request value.

Afterwards, change `pairing_request` to a new value and pair again. Every
previously paired phone must pair with the replacement identity.

## Troubleshooting

### The app stops immediately

Read the app log. The normal first start intentionally stops after displaying
the unapproved Samsung TLS fingerprint. Other common causes are an empty TV IP
or MAC address, an invalid fingerprint, the TV being asleep during initial
trust, or Companion port 49152 already being used.

### The remote target is not listed

- Confirm the app is running.
- Confirm the phone can reach HAOS on the Companion TCP port.
- Ensure multicast DNS UDP 5353 is not blocked.
- With VLANs, reflect the `_companion-link._tcp` service to the phone's VLAN.
- Do not run another instance with the same `device_name`.

### The first command is slow

The bridge opens Samsung's WebSocket when required. The first command after TV
wake can take a few seconds; subsequent commands reuse the connection.

### Wake-on-LAN does not work

Use the correct active-interface MAC and directed broadcast address. Enable the
Samsung setting that permits mobile/network power-on. Wake behavior varies by
model and firmware.

### Samsung reports a changed TLS certificate

Do not delete or bypass the pin. Clear `samsung_tls_fingerprint`, restart to
inspect the newly served certificate, verify it, then paste the new fingerprint
and restart once more.

## Persistent data and backups

HAOS app backups include `/data`. This contains the generated runtime config,
the emulated Apple TV identity, paired-phone public authorization, Samsung
token, TLS certificate pin, and one-shot request markers. Treat backups as
sensitive and restore all of this state together.

