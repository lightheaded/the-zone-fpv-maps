# Reproducible build environment for the pipeline. Runs native on amd64 and arm64.
# The Python wheels bundle GDAL and PROJ, so the image needs no system geodata packages.
#
# The image is built in two stages. The first stage needs a C++ compiler, because
# glcontext, which moderngl uses for the offscreen renderer, ships source only. The
# second stage keeps the virtual environment and the Mesa runtime, and no compiler.
FROM python:3.12-slim-bookworm AS build

# g++ and the GL headers build glcontext. They stay in this stage.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        g++ libx11-dev libgl1-mesa-dev libegl1-mesa-dev \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

WORKDIR /work

# Install dependencies first, so that a source change does not reinstall them.
COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --extra tour --no-install-project

COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --extra tour


FROM python:3.12-slim-bookworm

# The GDAL wheel links against libexpat, which the slim image does not ship. Mesa gives
# the renderer of "fpv-maps tour" a software OpenGL context. A container has no GPU, so
# a tour render in here is far slower than on a workstation.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libexpat1 libegl1 libgl1 libglx-mesa0 libgl1-mesa-dri libgbm1 \
    && rm -rf /var/lib/apt/lists/*

# Mesa draws without a display, and it draws in software.
ENV LIBGL_ALWAYS_SOFTWARE=1 \
    EGL_PLATFORM=surfaceless \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

WORKDIR /work

COPY --from=build /opt/venv /opt/venv
COPY src ./src
COPY pyproject.toml uv.lock README.md ./

ENTRYPOINT ["fpv-maps"]
CMD ["--help"]
