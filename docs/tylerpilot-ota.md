# TylerPilot — OTA & release tooling (design)

> **Status: design / prep only.** No promotion, no OTA execution. This document
> defines the target OTA/release architecture for the TylerPilot fork and the
> steps to get there. It is a commitment-time design, not a runbook that has been
> exercised on a device. The §6 decisions are **settled** (recorded below); the
> remaining work is implementation, gated on the build system (now restored).
>
> Companion: `AGENTS.md` (channel + release flow), `docs/cutover-runbook.md`
> (the *server* cutover — a different system).

---

## 1. Current state (as found)

### 1.1 The stock updater (`system/updated/updated.py`)
- **Mechanism:** `git ls-remote`/`git fetch` of `origin/<target_branch>` inside an
  **OverlayFS** staging area (`/data/safe_staging/{upper,metadata,merged}`), then
  `finalize_update()` copies the merged view to `/data/safe_staging/finalized`
  and writes the **`.overlay_consistent`** sentinel.
- **Activation:** at boot, `launch_chffrplus.sh` swaps the tree **only if**
  `BASEDIR/.overlay_init` exists, `BASEDIR/.git` is *not* newer than it, and
  `finalized/.overlay_consistent` exists:
  `mv $DIR /data/safe_staging/old_openpilot; mv finalized $DIR`. That
  `old_openpilot` copy is the **on-device rollback**.
- **Channels:** git branches. Target = `UpdaterTargetBranch` param, else the
  current branch, run through `SP_BRANCH_MIGRATIONS` (`system/version.py`).
- **Trust model:** **none.** The device trusts whatever `origin/<branch>` points
  at over HTTPS. There is **no signature/attestation** on the fetched tree.

### 1.2 TylerPilot's remote `update()` action (`sunnypilot/tylerpilot/actions.py`)
- Bypasses the stock updater: `git fetch --depth=1 origin <channel>` +
  `git checkout -f <channel>` + `git reset --hard` **in the live
  `/data/openpilot`**, then `rsync -a --delete` into
  `/data/safe_staging/finalized`, then `restart_manager`.
- **Gaps:** it does **not** create the overlay, does **not** write
  `.overlay_consistent`, and does **not** touch `.overlay_init` — so the boot-time
  swap in `launch_chffrplus.sh` may never activate it; it clobbers the running
  tree (no A/B); and it has **no signature check**. It also hardcodes
  `/data/openpilot` and the repo URL.
- **Recommendation:** route remote updates through the stock `updated` (or
  replicate its overlay + `.overlay_consistent`/`.overlay_init` contract). The
  raw bypass should be removed or made a thin "trigger a check/fetch" shim.

### 1.3 Channels & release flow (`AGENTS.md`)
- `dev-c3x` → `staging-c3x` → `release-c3x` (ancestor invariant).
- A release = bump `sunnypilot/common/version.h` → signed tag `v<version>` →
  GitHub Release. Version format `YYYY.MM.PPP`.
- The comma 3X tracks `release-c3x` and hard-resets to its head on each check —
  **anything on `release-c3x` ships immediately**.

### 1.4 Upstream reference (archive)
- Upstream `sunnypilot` builds a **stripped branch** (`tools/release/build_stripped.sh`)
  and OTA is branch-based — **no artifact signing** upstream either.

### 1.5 Build system — RESOLVED
- **Root cause:** the fork's branches were cut from a sunnypilot **prebuilt
  branch** (`release-tizi-staging` @ `831d268e85`, tree == the fork snapshot root
  `6a17f75c6b`). A prebuilt branch is a **stripped build output**: upstream's
  `sunnypilot-build-prebuilt.yaml` deletes `SConstruct`, every `SConscript` and
  the `*.onnx` models, then adds an empty `prebuilt` marker. So the build
  entrypoint was absent **by construction**, and `launch_chffrplus.sh` skips
  `system/manager/build.py` whenever the marker is present.
- **Fix:** the build system was restored from the sunnypilot master commit the
  staging tree was built from (`c440933a65` == tag `v2026.002.002`): `SConstruct`
  + 18 `SConscript` files + the three ONNX models (real LFS content), and the
  stale `prebuilt` marker dropped. The CI `build` job and `release.yml` now run a
  real `scons` build.

---

## 2. Goals

1. **Signed releases** — a device applies an update only if it can verify it was
   produced by us (no silent/compromised-remote shipping to the car).
2. **Channel / staged rollout** — promote dev→staging→release, and roll a release
   out **gradually** to the fleet (rings/percentage) rather than all-at-once,
   with the ability to **pause**.
3. **Rollback** — a one-command fleet rollback and a documented on-device
   rollback, both fast and reversible.

---

## 3. Target architecture

### 3.1 Release artifacts
On a signed tag `v<version>` on `release-c3x`, a `release.yml` workflow:
1. **Builds** the stripped tree (gated on the build being restored; see §1.5).
2. Produces a **release manifest** (`release.json`):
   ```json
   {
     "channel": "release-c3x",
     "version": "2026.002.030",
     "commit": "<full sha of the tag>",
     "tree_hash": "<sha256 of the built tree>",
     "min_agnos": "…",
     "rollout": { "ring": "canary", "percent": 5 },
     "published_at": "2026-…Z"
   }
   ```
3. **Signs** the manifest (§3.2) and attaches `release.json` + signature as
   **GitHub Release assets**.

> The device keeps trusting the **git branch** for the code content (as today),
> but additionally verifies the **signed manifest** (version↔commit↔rollout)
> before applying. This is the smallest change that adds real trust without
> replacing the branch-based OTA.

### 3.2 Signing — **DECIDED: pinned Ed25519 key in `bws`**
- **DECISION:** **B. Pinned offline key (Ed25519).** Generate a signing key pair
  offline; the **public** key is pinned in the firmware; the **private** key lives
  in `bws` and is only unsealed in the release workflow. This matches KvmCloud and
  is consistent fleet-wide. Sigstore keyless is a **later** option.
- *(Rejected for now)* **A. Keyless (Sigstore/cosign + GitHub OIDC)** — no
  long-lived key, but requires shipping a cosign/Sigstore verifier on-device.

The pinned public key ships in `sunnypilot/tylerpilot/` and is what the agent's
update path checks.

### 3.3 Channel & staged rollout — **DECIDED: `stable`/`beta`, admin-set per device**
- **DECISION:** two channels, **`stable`** and **`beta`**, with the channel
  **set per device by an admin** (matches KVM's channel model). Percent/ring
  rollout is a **later** refinement.
- **Channels stay git branches** (`dev-c3x`/`staging-c3x`/`release-c3x`) for
  integration and pre-release testing; the device's `stable`/`beta` selection
  picks which published branch/manifest it tracks.
- *(Later)* **Staged rollout** driven by the **signed manifest's `rollout`
  field** — a stable **ring** assignment (hash of device id → `canary`/`beta`/
  `stable`) or a **percent** gate; the agent applies only if
  `ring ∈ manifest.rollout.rings` (or `hash(device_id) % 100 < percent`).
  **Pausing** = publish a manifest with `percent: 0` (or drop the ring).

### 3.4 Device update path (target) — **DECIDED: fix `update()` to use the stock updater**
- **DECISION:** the TylerPilot `update()` action is **fixed to route through the
  stock `updated`** (or to replicate its OverlayFS + `.overlay_consistent`/
  `.overlay_init` contract). The current raw `git checkout -f` into the live tree
  is an integrity gap and likely never activates; it is removed.
```
agent → fetch release.json (+ .sig) for channel
      → verify signature against pinned key
      → check channel (stable/beta) gate
      → hand off to stock updated (branch fetch + overlay + finalize)
      → boot swap activates; old_openpilot retained for rollback
```
No more raw `checkout -f` into the live tree.

---

## 4. Rollback runbook

### 4.1 Fleet rollback (bad release)
1. **Stop the rollout:** publish a manifest with `percent: 0` (or drop the ring) →
   no new devices apply.
2. **Revert the channel:** `git revert`/reset `release-c3x` to the previous
   signed tag's commit (fast-forward back), or move the branch back:
   `git push --force-with-lease origin <prev_sha>:release-c3x` (only if the
   ancestor invariant is preserved — reverting via a new commit is preferred).
3. **Re-sign:** bump `version.h` if needed, re-tag/re-release with a manifest
   pointing at the reverted commit; devices re-fetch on the next check.
4. **Verify:** confirm devices report the reverted version (`UpdaterCurrentDescription`).

### 4.2 On-device rollback (single device / bricked update)
- `launch_chffrplus.sh` keeps the prior tree at `/data/safe_staging/old_openpilot`.
  Roll back by swapping it back:
  ```
  mv /data/openpilot /data/safe_staging/bad_update
  mv /data/safe_staging/old_openpilot /data/openpilot
  reboot
  ```
- If no `old_openpilot` exists, pin the device to a known-good commit via
  `UpdaterTargetBranch` + a branch/commit, or SSH-reflash (device is reachable
  over the TylerPilot tunnel / `pilot-connect` `:8022`).

### 4.3 Emergency stop
- `DisableUpdates` param halts the stock updater immediately (per device);
  `UpdaterState` surfaces the current phase.

---

## 5. Deliverables / plan

| # | Item | Depends on |
|---|---|---|
| D1 | This design doc | — |
| D2 | `release.yml` (build → manifest → sign → Release) | build (SConstruct) |
| D3 | Signed-manifest verifier + channel gate in the agent (replaces the raw `update()` bypass) | signing (§6) |
| D4 | Pinned public key in firmware; private key in `bws` | principal |
| D5 | Rollback drill on one device (staging channel) | a device + staging promotion |

D1 shipped. The build system is **restored** (root `SConstruct`/`SConscript` +
ONNX models; see the restore commit) and `release.yml` now **builds and packages**
`prebuilt.tar.gz`. Remaining: D2's signing step, and D3–D5.

---

## 6. Decisions (settled)

1. **Signing:** **pinned Ed25519 key in `bws`** (matches KvmCloud; consistent
   fleet-wide). Sigstore keyless is a later option. → §3.2
2. **Channels:** **`stable`/`beta`, admin-set per device** (matches KVM's
   channel model). Percent/ring rollout is a later refinement. → §3.3
3. **Trust scope:** **verify the manifest only** for now (code still trusted via
   git); signed artifacts wholesale is a later option.
4. **`update()` action:** **fix it to route through the stock `updated`** (the
   raw bypass is an integrity gap and likely never activates). → §3.4
5. **Min-AGNOS:** **encode the minimum AGNOS version in the manifest.**
