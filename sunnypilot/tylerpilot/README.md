# TylerPilot Cloud (device)

Links a comma 3X to a TylerPilot server for stats and remote SSH.

## Where it lives

- `config.py` — link state, stored 0600 at `/data/community/tylerpilot.json`
  (Params can't take new keys on this branch, so state is a file).
- `client.py` — stdlib-only HTTPS client with **certificate pinning**. The
  server cert fingerprint is captured on first registration (trust-on-first-use,
  authorized by the pairing code) and verified on every later connection.
- `agent.py` — background process `tylerpilotd`: heartbeat + 25s long-poll for
  commands. Idles when not linked. Heartbeat is 15s on every link type.
- `log.py` — TylerPilot-only log, capped at **50 MB** (see Logs below).
- `../selfdrive/ui/.../settings/tylerpilot.py` — the Settings panel
  (**Settings → Developer → TylerPilot Cloud**).

## Linking

1. Server web UI → **Add device** → copy the 12-digit code (valid 10 min).
2. On the device: **Settings → Developer → TylerPilot Cloud → Link**, type the code.
3. The device generates an ed25519 tunnel key, registers, installs the server's
   login key into `/home/comma/.ssh/authorized_keys`, and starts heartbeating.

## Server address

Hardcoded for the PoC in `config.py`:

```python
DEFAULT_HOST = "pilot-connect.tylerjp.com"
DEFAULT_PORT = 8021  # API (TLS passthrough to the backend)
DEFAULT_SSH_PORT = 8022  # reverse-SSH tunnel
```

## Logs

TylerPilot keeps its own log, deliberately **separate from openpilot's swaglog**
so it never touches sunnypilot's logs:

- Path: `/data/community/tylerpilot.log`
- Cap: **50 MB** — on overflow the file is trimmed down to its most recent half,
  so total size stays under the cap without a hard stop.
- Written by `log.py` (`info` / `warning` / `error`); the agent no longer sends
  its messages to `cloudlog`.

## Remote SSH

When an admin clicks **SSH** in the web UI, the server queues a command with a
loopback port; the agent's next poll opens
`ssh -N -R 127.0.0.1:<port>:localhost:22 tunnel@<server>`. The server then
bridges a browser terminal through it. The tunnel key is locked to
`permitlisten="127.0.0.1:*"` and `no-pty` on the server.
