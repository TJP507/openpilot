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
3. The device registers over the pinned cert, installs the server's login key into
   `/home/comma/.ssh/authorized_keys`, and starts heartbeating.

## Server address

Hardcoded for the PoC in `config.py`:

```python
DEFAULT_HOST = "pilot-connect.tylerjp.com"
DEFAULT_PORT = 443  # single port: device API + SSH-over-WebSocket tunnel
```

The reverse proxy SNI-routes `pilot-connect.tylerjp.com` on 443 as raw TCP
(no TLS termination, so the device still sees the pinned cert). 443 is used
because restrictive networks allow it far more often than the old 8021.

## Logs

TylerPilot keeps its own log, deliberately **separate from openpilot's swaglog**
so it never touches sunnypilot's logs:

- Path: `/data/community/tylerpilot.log`
- Cap: **50 MB** — on overflow the file is trimmed down to its most recent half,
  so total size stays under the cap without a hard stop.
- Written by `log.py` (`info` / `warning` / `error`); the agent no longer sends
  its messages to `cloudlog`.

## Remote SSH (single port)

The device talks to the server over **one port** (`DEFAULT_PORT`): the device API
(register/heartbeat/poll) *and* the SSH tunnel. When an admin clicks **SSH** in
the web UI, the server queues an `ssh_request` with a session id; the agent's
next poll opens a **WebSocket** to `wss://<server>:<port>/api/v1/device/ssh-bridge`
on that same port and bridges it to this device's sshd (`localhost:22`). The
server runs `ssh` against the bridged stream and pipes a browser terminal through
it. No separate SSH port or reverse `ssh -R` is needed.
