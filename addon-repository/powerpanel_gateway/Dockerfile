# PowerPanel Gateway add-on image.
#
# Built on the Home Assistant Debian base images (see build.yaml). Debian/glibc
# on purpose: CyberPower PowerPanel ships glibc binaries that do NOT run on
# Alpine/musl, so a Debian base is what lets real-UPS mode work in the add-on.
#
# The gateway runs in mock mode out of the box. For a real UPS, drop your
# CyberPower PowerPanel .deb into this add-on's `vendor/` folder before building
# (see DOCS.md, "Real UPS mode"). We never download PowerPanel for you.
#
# BUILD_FROM defaults to the amd64 Debian base so a plain `docker build` works
# locally; the Home Assistant builder overrides BUILD_FROM per-arch via build.yaml.
ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base-debian:bookworm
FROM ${BUILD_FROM}

ENV LANG=C.UTF-8 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Runtime deps. python3 + venv to run the gateway; jq for run.sh's options
# parsing; usbutils/udev/libusb so PowerPanel can find the UPS HID device.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        python3 \
        python3-venv \
        jq \
        usbutils \
        udev \
        libusb-1.0-0 \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps into an isolated venv (also gives us a `python` command).
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && rm /tmp/requirements.txt

# Application code (the importable package lives under rootfs/app).
COPY rootfs /
ENV PYTHONPATH=/app

# Optional user-supplied CyberPower PowerPanel package(s) for real-UPS mode.
# The directory always exists (contains a .gitkeep); install is a no-op without
# a .deb, so mock mode keeps working.
COPY vendor/ /tmp/vendor/
RUN set -e; \
    if ls /tmp/vendor/*.deb >/dev/null 2>&1; then \
        echo "Installing user-supplied CyberPower PowerPanel package(s)..."; \
        apt-get update; \
        apt-get install -y --no-install-recommends /tmp/vendor/*.deb; \
        rm -rf /var/lib/apt/lists/*; \
    else \
        echo "No PowerPanel .deb in vendor/; image will run in mock mode only."; \
    fi; \
    rm -rf /tmp/vendor

WORKDIR /app
LABEL io.hass.type="addon"

CMD [ "/run.sh" ]
