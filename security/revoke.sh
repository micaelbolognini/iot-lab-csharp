#!/usr/bin/env bash
# Usage: revoke.sh OUTDIR DEVICE  - revokes one device certificate and rewrites the CRL.
# The broker reads the CRL on start, so restart it afterwards.
set -euo pipefail
OUT=${1:?usage: revoke.sh OUTDIR DEVICE}
NAME=${2:?usage: revoke.sh OUTDIR DEVICE}
OUT=$(cd "$OUT" && pwd); cd "$OUT"
[ -f "devices/$NAME.crt" ] || { echo "unknown device: $NAME" >&2; exit 1; }
openssl ca -config ca.cnf -cert ca.crt -keyfile ca.key -revoke "devices/$NAME.crt" 2>/dev/null
openssl ca -config ca.cnf -cert ca.crt -keyfile ca.key -gencrl -out crl.pem 2>/dev/null
echo "revoked $NAME"
