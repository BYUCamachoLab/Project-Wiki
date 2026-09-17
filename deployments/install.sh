#!/usr/bin/env bash
# Install/refresh this repo's systemd units. Run with sudo.
#   sudo bash install.sh
set -euo pipefail
cd "$(dirname "$0")"
UNITS=(camacholab-caddy.service)
for u in "${UNITS[@]}"; do
  install -m 0644 "$u" "/etc/systemd/system/$u"
  echo "installed /etc/systemd/system/$u"
done
systemctl daemon-reload
for u in "${UNITS[@]}"; do systemctl enable "$u"; done
echo
echo "Enabled. Start now with:  sudo systemctl start ${UNITS[*]}"
