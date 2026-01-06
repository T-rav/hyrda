#!/bin/sh
set -e

# Generate SSL certificates using shared script
sh /app/shared/scripts/generate-ssl-certs.sh control-plane localhost control-plane 127.0.0.1 ::1

# Start the FastAPI app with Uvicorn
exec uvicorn app:app --host 0.0.0.0 --port 6001 --workers 4 \
    --ssl-keyfile ssl/key.pem \
    --ssl-certfile ssl/cert.pem
