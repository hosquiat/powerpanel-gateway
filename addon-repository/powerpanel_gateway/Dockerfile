# PowerPanel Gateway add-on image.
#
# Built on the official Home Assistant Python base images (see build.yaml).
# IMPORTANT: this image does NOT bundle CyberPower PowerPanel. PowerPanel for
# Linux is proprietary and is not redistributable here. The gateway runs fine in
# mock mode out of the box; to talk to a real UPS you must add PowerPanel to the
# image yourself (see DOCS.md, "Real UPS mode").
#
# BUILD_FROM defaults to the amd64 Home Assistant Python base so a plain
# `docker build` works locally (it ships bashio + s6, which run.sh uses). The
# Home Assistant builder overrides BUILD_FROM per-arch via build.yaml. On Apple
# Silicon the amd64 default runs under emulation; pass --build-arg BUILD_FROM=...
# with the aarch64 base for a native local build.
ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base-python:3.12-alpine3.20
FROM ${BUILD_FROM}

ENV LANG=C.UTF-8 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Runtime + build deps. Build deps are installed in a virtual package and removed
# after pip so the final image stays small. cargo/rust are present in case a
# musllinux wheel for pydantic-core is unavailable for this arch.
RUN apk add --no-cache \
        eudev \
        usbutils \
    && apk add --no-cache --virtual .build-deps \
        gcc \
        musl-dev \
        libffi-dev \
        cargo

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt \
    && apk del .build-deps \
    && rm -rf /root/.cargo /tmp/requirements.txt

# Application code (the importable package lives under rootfs/app).
COPY rootfs /
ENV PYTHONPATH=/app

# Optional: to build real-UPS support, place a PowerPanel package in this build
# context and uncomment the matching line. We never download it for you.
#   COPY powerpanel.deb /tmp/powerpanel.deb && dpkg -i /tmp/powerpanel.deb   # (Debian base only)

WORKDIR /app
LABEL io.hass.type="addon"

CMD [ "/run.sh" ]
