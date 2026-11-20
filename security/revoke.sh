#!/usr/bin/env bash
# Usage: revoke.sh OUTDIR DEVICE  - revokes one device or opcua/ certificate and rewrites the CRL.
# The broker reads the CRL on start, so restart it afterwards.
set -euo pipefail
OUT=${1:?usage: revoke.sh OUTDIR DEVICE}
NAME=${2:?usage: revoke.sh OUTDIR DEVICE}
OUT=$(cd "$OUT" && pwd); cd "$OUT"
export OPCUA_APP=unused # ca.cnf reads this env var
# NAME is a device (gateway-cs) or an OPC UA app cert (opcua/gateway-cs)
case "$NAME" in
  opcua/*) CERT="$NAME.crt" ;;
  *) CERT="devices/$NAME.crt" ;;
esac
[ -f "$CERT" ] || { echo "unknown device: $NAME" >&2; exit 1; }
openssl ca -config ca.cnf -cert ca.crt -keyfile ca.key -revoke "$CERT" 2>/dev/null
openssl ca -config ca.cnf -cert ca.crt -keyfile ca.key -gencrl -out crl.pem 2>/dev/null
openssl crl -in crl.pem -outform der -out opcua/pki/trusted/crl/ca.crl
echo "revoked $NAME"
