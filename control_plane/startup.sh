#!/bin/sh
set -e

# Internal services use HTTP - nginx handles SSL termination
exec uvicorn app:app --host 0.0.0.0 --port 6001 --workers 4
