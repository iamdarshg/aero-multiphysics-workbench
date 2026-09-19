# syntax=docker/dockerfile:1.7
#
# Pinned worker image for the heavy native stack: OpenFOAM, Code_Aster, Elmer,
# preCICE plus the Python 3.12 participant stack (ROSS / PyBaMM / OpenMDAO /
# Gmsh / CadQuery + Cantera). Generic infrastructure -- no application cases.
#
# Layer contract (build cache): OS + PPA + micromamba + conda solver prefixes
# are pinned by digest/version and sit above the first COPY, so a participant
# code change never rebuilds a solver layer. The repository is NOT baked in;
# the governed participant path runs from a commit-pinned checkout mounted at
# /opt/repo at first start.
#
# Build (context is the repository root):
#   docker buildx build --platform linux/amd64 \
#     -f infra/docker/worker/native-solvers.Dockerfile \
#     --tag "$REGISTRY/aero-worker-native:2026.09" \
#     --provenance=true --sbom=true --load .
#
# Base image: ubuntu:22.04 (digest in pins.json baseImages.native-solvers).
# Elmer ships only through the elmer-csc PPA; jammy is its supported series.

FROM ubuntu:22.04@sha256:b8b6ee6aa931ecd9d0d952abc34dc0e5f7c6a30c6bb71b079fe399fde0329c02 AS native-solvers

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ARG WORKER_UID=10001
ARG WORKER_GID=10001
ARG UV_VERSION=0.9.6
ARG CANTERA_VERSION=3.2.0
ARG MICROMAMBA_VERSION=2.0.5-0
ARG MICROMAMBA_SHA256=bfc2e3a414d651af7508c49998a12b5cf3c7029d56c5ef37c9a3248cd7faef78
ARG WORKER_BASE_REF=ubuntu:22.04
ARG WORKER_BASE_DIGEST=sha256:b8b6ee6aa931ecd9d0d952abc34dc0e5f7c6a30c6bb71b079fe399fde0329c02

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_LINK_MODE=copy \
    WORKER_ROLE=native-solvers \
    WORKER_IMAGE=aero-worker-native \
    WORKER_BASE_REF=${WORKER_BASE_REF} \
    WORKER_BASE_DIGEST=${WORKER_BASE_DIGEST}

# --- Layer 1: OS runtime libraries (pinned by the digest-fixed base) --------
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        software-properties-common ca-certificates curl bzip2 patch \
        xvfb libgl1 libglu1-mesa libopenblas0 libgomp1 \
    && add-apt-repository -y ppa:deadsnakes/ppa \
    && add-apt-repository -y ppa:elmer-csc-ubuntu/elmer-csc-ppa \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        "python3.12=3.12.13-1+jammy1" \
        "python3.12-venv=3.12.13-1+jammy1" \
        "elmerfem-csc=9.0-0ppa0-202609171021~9ef450fbb~ubuntu22.04.1" \
    && rm -rf /var/lib/apt/lists/* \
    && python3.12 -c "import sys; assert sys.version_info[:2] == (3, 12), sys.version" \
    && command -v ElmerSolver >/dev/null

# --- Layer 2: micromamba (version + sha256 pinned, verified before use) -----
RUN curl -fsSL \
        "https://github.com/mamba-org/micromamba-releases/releases/download/${MICROMAMBA_VERSION}/micromamba-linux-64.tar.bz2" \
        -o /tmp/micromamba.tar.bz2 \
    && printf '%s  %s\n' "${MICROMAMBA_SHA256}" /tmp/micromamba.tar.bz2 | sha256sum -c - \
    && tar -xjf /tmp/micromamba.tar.bz2 -C /usr/local/bin --strip-components=1 bin/micromamba \
    && rm -f /tmp/micromamba.tar.bz2 \
    && micromamba --version

# --- Layer 3: conda-forge solver prefixes (versions pinned) -----------------
# openfoam and precice drag incompatible MPI/PETSc stacks; keep independent
# prefixes so neither evicts the other.
RUN micromamba create -y -p /opt/solvers/openfoam -c conda-forge "openfoam=2412" \
    && micromamba create -y -p /opt/solvers/precice -c conda-forge "precice=3.2.0" "pyprecice=3.2.0" \
    && micromamba create -y -p /opt/solvers/code-aster -c conda-forge "code-aster=18.1.6" \
    && micromamba create -y -p /opt/solvers/mesh -c conda-forge "gmsh=4.15.2" \
    && micromamba clean -a -y \
    && test -x /opt/solvers/openfoam/bin/simpleFoam \
    && test -x /opt/solvers/precice/bin/precice-config-visualizer \
    && test -x /opt/solvers/code-aster/bin/as_run \
    && test -x /opt/solvers/mesh/bin/gmsh

# --- Layer 4: Python 3.12 participant stack (repo uv.lock, cantera additive) -
RUN python3.12 -m ensurepip --upgrade \
    && python3.12 -m pip install --no-cache-dir "uv==${UV_VERSION}"
WORKDIR /opt/participants
COPY services/api/pyproject.toml services/api/uv.lock ./
RUN uv sync --frozen --no-dev --python /usr/bin/python3.12 --link-mode=copy \
    && uv pip install --python /opt/participants/.venv/bin/python "cantera==${CANTERA_VERSION}" \
    && /opt/participants/.venv/bin/python - <<'PY'
import importlib.metadata as m
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
print("native python participant lock verified")
PY

# --- Layer 5: worker tooling (small, cache-independent of solvers) ----------
COPY infra/docker/worker/ /opt/worker/
RUN chmod +x /opt/worker/emit-capability-manifest.sh /opt/worker/worker-entrypoint.sh

ENV PATH=/opt/solvers/openfoam/bin:/opt/solvers/precice/bin:/opt/solvers/code-aster/bin:/opt/solvers/mesh/bin:/opt/participants/.venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
    LD_LIBRARY_PATH=/opt/solvers/openfoam/lib:/opt/solvers/precice/lib:/opt/solvers/code-aster/lib:/opt/solvers/mesh/lib \
    WORKER_PYTHON=/opt/participants/.venv/bin/python

# Non-root worker; solver prefixes stay read-only to the user and jobs write
# only to the mounted /data root. No credentials are copied.
RUN groupadd --gid "${WORKER_GID}" worker \
    && useradd --uid "${WORKER_UID}" --gid "${WORKER_GID}" --create-home --shell /usr/sbin/nologin worker \
    && chown -R worker:worker /opt/solvers /opt/participants /opt/worker \
    && mkdir -p /data/jobs && chown worker:worker /data

USER worker
ENV HOME=/home/worker
RUN /opt/worker/emit-capability-manifest.sh /opt/worker/capability-manifest.json

VOLUME ["/data"]
ENTRYPOINT ["/opt/worker/worker-entrypoint.sh"]
CMD ["capabilities"]
