# Standalone (non-add-on) deployment image for a machine that has the CyberPower
# UPS plugged in over USB. Use this when the UPS is NOT on your Home Assistant
# host (e.g. Home Assistant OS) but on a separate Linux box you control.
#
# Debian-based on purpose: CyberPower PowerPanel ships glibc binaries, which do
# NOT run on the Alpine-based Home Assistant add-on image. Here they install
# cleanly.
#
# Build from the REPO ROOT so the gateway package is in context:
#   docker build -f deploy/Dockerfile -t powerpanel-gateway:real .
#
# Real-UPS mode: drop your CyberPower PowerPanel .deb into deploy/vendor/ before
# building. With no .deb present the image still builds and runs in mock mode.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    POWERPANEL_GATEWAY_DATA_DIR=/data \
    PYTHONPATH=/app

# Runtime deps. usbutils/udev help PowerPanel find the UPS HID device.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        usbutils \
        udev \
        libusb-1.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Gateway dependencies + package source (single source of truth under the add-on
# rootfs, copied here so this image and the add-on stay identical).
COPY addon-repository/powerpanel_gateway/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && rm /tmp/requirements.txt
COPY addon-repository/powerpanel_gateway/rootfs/app/ /app/

# Optional user-supplied CyberPower PowerPanel package(s). The directory always
# exists (it contains a .gitkeep); the install step is a no-op without a .deb.
COPY deploy/vendor/ /tmp/vendor/
RUN set -e; \
    if ls /tmp/vendor/*.deb >/dev/null 2>&1; then \
        echo "Installing user-supplied PowerPanel package(s)..."; \
        apt-get update; \
        apt-get install -y --no-install-recommends /tmp/vendor/*.deb; \
        rm -rf /var/lib/apt/lists/*; \
    else \
        echo "No PowerPanel .deb in deploy/vendor/; image will only work in mock mode."; \
    fi; \
    rm -rf /tmp/vendor

COPY deploy/run.sh /run.sh
RUN chmod +x /run.sh

EXPOSE 8099
VOLUME ["/data"]
LABEL org.opencontainers.image.title="powerpanel-gateway (standalone)" \
      org.opencontainers.image.licenses="GPL-3.0-or-later"

CMD ["/run.sh"]
