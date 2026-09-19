# syntax=docker/dockerfile:1.7
#
# Pinned worker image for the Python 3.12 participant stack
# (ROSS / PyBaMM / OpenMDAO / Gmsh / CadQuery + Cantera). No native solver
# binaries and no application cases are baked in.
#
# Layer contract (build cache): the dependency layer is driven only by the
# base digest + services/api/uv.lock, so a participant-only code change never
# invalidates it. The repo is intentionally NOT copied into the image; the
# governed participant path runs from a commit-pinned checkout mounted at
# /opt/repo at first start.
#
# Build (context is the repository root):
#   docker buildx build --platform linux/amd64 \
#     -f infra/docker/worker/participants-python.Dockerfile \
#     --tag "$REGISTRY/aero-worker-python:2026.09" \
#     --provenance=true --sbom=true --load .
#
# Base image: python:3.12-slim-bookworm
# Digest pinned in infra/docker/worker/pins.json (baseImages.participants-python).

FROM python:3.12-slim-bookworm@sha256:d5ae74acb8026b32a2f6deea45003c5bd4e2880700c19c44bda54670ad3eff90 AS participants-python

ARG WORKER_UID=10001
ARG WORKER_GID=10001
ARG UV_VERSION=0.9.6
ARG CANTERA_VERSION=3.2.0
ARG WORKER_BASE_REF=python:3.12-slim-bookworm
ARG WORKER_BASE_DIGEST=sha256:d5ae74acb8026b32a2f6deea45003c5bd4e2880700c19c44bda54670ad3eff90

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_LINK_MODE=copy \
    WORKER_ROLE=python-participants \
    WORKER_IMAGE=aero-worker-python \
    WORKER_BASE_REF=${WORKER_BASE_REF} \
    WORKER_BASE_DIGEST=${WORKER_BASE_DIGEST}

# gmsh/cadquery wheels link libGL/libGLU even headless; SciPy/CasADi need
# libopenblas and libgomp. This is the minimal runtime set, pinned by the
# digest-fixed base plus the frozen package lists in the base image.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libglu1-mesa libgl1 libstdc++6 libopenblas0 libgomp1 ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# uv is pinned to the base interpreter; the CI gate asserts Python >= 3.12.
RUN pip install --no-cache-dir "uv==${UV_VERSION}" \
    && /usr/local/bin/python3.12 -c "import sys; assert sys.version_info[:2] == (3, 12), sys.version"

# Frozen Python participant lock reused from the repository (hash-verified by
# uv). Cantera is an additive catalog solver absent from the API lock, so it is
# pinned separately and never floats.
WORKDIR /opt/participants
COPY services/api/pyproject.toml services/api/uv.lock ./
RUN uv sync --frozen --no-dev --python /usr/local/bin/python3.12 --link-mode=copy \
    && uv pip install --python /opt/participants/.venv/bin/python "cantera==${CANTERA_VERSION}" \
    && /opt/participants/.venv/bin/python - <<'PY'
import importlib.metadata as m
import sys
assert sys.version_info[:2] == (3, 12), sys.version
expected = {
    "ross-rotordynamics": "2.3.0",
    "pybamm": "26.8.0.0",
    "openmdao": "3.45.1",
    "gmsh": "4.15.2",
    "cadquery": "2.8.0",
    "casadi": "3.7.2",
    "numpy": "2.5.3",
    "scipy": "1.18.1",
    "cantera": "3.2.0",
}
for name, version in expected.items():
    actual = m.version(name)
    assert actual == version, f"{name} expected {version}, got {actual}"
print("participants-python lock verified")
PY

# Worker tooling: capability emitter + allowlisted entrypoint. This layer is
# tiny and changes independently of the solver layers above.
COPY infra/docker/worker/ /opt/worker/
RUN chmod +x /opt/worker/emit-capability-manifest.sh /opt/worker/worker-entrypoint.sh

# Non-root worker: solver prefixes are read-only to the user; jobs write only
# to the mounted /data job root. No credentials are ever copied.
RUN groupadd --gid "${WORKER_GID}" worker \
    && useradd --uid "${WORKER_UID}" --gid "${WORKER_GID}" --create-home --shell /usr/sbin/nologin worker \
    && chown -R worker:worker /opt/participants /opt/worker \
    && mkdir -p /data/jobs && chown worker:worker /data

# Emit the build-time capability receipt as the worker user (same environment
# the runtime probes will observe).
USER worker
ENV HOME=/home/worker \
    PATH=/opt/participants/.venv/bin:/usr/local/bin:/usr/bin:/bin
RUN /opt/worker/emit-capability-manifest.sh /opt/worker/capability-manifest.json

VOLUME ["/data"]
ENTRYPOINT ["/opt/worker/worker-entrypoint.sh"]
CMD ["capabilities"]
