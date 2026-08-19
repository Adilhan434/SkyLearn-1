#!/bin/sh
set -eu

# Named volumes are created as root and must be prepared before dropping privileges.
if [ "$(id -u)" = "0" ]; then
    mkdir -p /app/media /app/private_media
    chown -R app:app /app/media /app/private_media
    exec setpriv --reuid=app --regid=app --init-groups "$@"
fi

exec "$@"
