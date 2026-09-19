# Containers and cloud boundary

The local Docker and Terraform files are reviewable manifests, not deployment evidence. There are no image digests, pushed images, Terraform state, provisioned resources, cloud URLs, or billing receipts in this worktree.

For a future controlled deployment: review pinned base-image policy, build and scan an image, record its digest, configure an isolated GCP project and retention policy, establish a hard user-approved cost envelope/budget alerts, run and retain `terraform plan`, explicitly set `enable_remote_compute=true`, apply with an authenticated operator, then record actual resource identifiers and job/result provenance. Keep remote authorization separate from local capability readiness.

## Pinned native-solver worker images (issue #43)

The lightweight product-plane image (`infra/docker/Dockerfile.platform`) deliberately excludes native solver binaries. The heavy native stack is now packaged separately as a small, bounded set of **pinned worker images** under `infra/docker/worker/`, so a fresh VM starts from a known solver environment instead of installing solvers on boot.

| Image | Dockerfile | Covers |
|---|---|---|
| `worker-python` | `infra/docker/worker/participants-python.Dockerfile` | Python 3.12 participants: ROSS, PyBaMM, OpenMDAO, Gmsh, CadQuery, Cantera |
| `worker-native` | `infra/docker/worker/native-solvers.Dockerfile` | OpenFOAM, Code_Aster, Elmer, preCICE **plus** the Python participant stack |

Both bases are pinned by immutable digest and every solver/package/OS pin lives in one machine-readable file, `infra/docker/worker/pins.json`:

- base images: `python:3.12-slim-bookworm@sha256:d5ae74ac…`, `ubuntu:22.04@sha256:b8b6ee6a…`
- OS/runtime libraries via the digest-fixed base plus the elmer-csc and deadsnakes PPAs pinned to exact versions (`elmerfem-csc=9.0-0ppa0-202609171021~9ef450fbb~ubuntu22.04.1`, `python3.12=3.12.13-1+jammy1`)
- micromamba `2.0.5-0`, downloaded from a version-pinned URL and verified against a recorded SHA-256 before extraction
- conda-forge solver prefixes: `openfoam=2412`, `precice=3.2.0` + `pyprecice=3.2.0`, `code-aster=18.1.6`, `gmsh=4.15.2`
- Python participant lock reused from the repository's hash-verified `services/api/uv.lock` (ROSS 2.3.0, PyBaMM 26.8.0.0, OpenMDAO 3.45.1, Gmsh 4.15.2, CadQuery 2.8.0, CasADi 3.7.2) plus `cantera==3.2.0`

No floating `latest` tag is permitted in trusted execution; `scripts/gcp/worker-image-validate.mjs` (and `node --test tests/unit/worker-image.test.ts`) fails closed on any digest/version drift or `latest`.

### Capability manifest

At build and at first start the image emits a machine-readable capability receipt (`infra/docker/worker/emit_capability_manifest.py`, schema `infra/docker/worker/capability-manifest.schema.json`): exact executable paths + `--version` strings, and Python library versions via `importlib.metadata` only. `scripts/gcp/worker-smoke.py` compares this manifest against live runtime participant probing (`solvers/participants/capabilities.py`); a mismatch is fatal, so native results cannot publish from an image that does not match its declared capabilities.

The image records exactly what the runtime prober will observe, including the existing probe contract: readiness for an executable family is decided by its `--version` return code (e.g. OpenFOAM `simpleFoam --version`). If that probe does not succeed, both the manifest and the runtime report `unavailable` and stay fail-closed; changing the probe contract is owned by SOLVER-CORR, not by this image work.

### Build, smoke, and evidence status

The `#43` build host had **no Docker daemon**, so images were validated statically only. The exact build command (to be run on a Docker/BuildKit host) is:

```
scripts/gcp/build-worker-images.sh --registry REGISTRY/REPO [--push]
```

It uses BuildKit layer caching, SBOM, and provenance, then records the immutable image digests into `infra/docker/worker/pins.resolved.json`. The `recorded` block in `pins.json` is marked `PENDING` with an explicit reason until that runs. `scripts/gcp/worker-image-startup.sh` is the refactored VM startup: it pulls the image by digest, verifies the pulled digest, emits the capability manifest, runs the bounded smoke proof from a commit-pinned checkout, and fails closed on any mismatch. It never installs a solver.

The worker images are generic infrastructure: no application cases are baked in, and solver correctness remains owned by SOLVER-CORR — image build success is not a correctness claim.

### Startup time / cost (before vs after)

**Measurement status: PENDING** (no Docker daemon on the `#43` host, so no build+VM run happened). The baseline is the superseded **before** path — `infra/gcp/solver-worker-startup.sh` resolves and installs OpenFOAM/preCICE/Code_Aster/Elmer + Python 3.12 at every worker boot. The target **after** path (`scripts/gcp/worker-image-startup.sh`) pulls one digest-pinned image and runs a seconds-scale smoke. No before/after numbers are recorded here because none were measured; do not treat the target as measured until a bounded GCP run captures both.

### GCP spend (issue #43)

$0.00 — no VM or GCP resource was launched for this issue (static validation only).

