#!/usr/bin/env bash
# Usage: setup.sh OUTDIR  - creates CA, server cert, one client cert per device, CRL, ACL and broker config.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
OUT=${1:?usage: setup.sh OUTDIR}
GATEWAYS=(gateway-py gateway-cs gateway-java)
MONITORS=(monitor)
mkdir -p "$OUT"; OUT=$(cd "$OUT" && pwd); cd "$OUT"
umask 077
mkdir -p newcerts devices
: > index.txt
echo 01 > serial
echo 01 > crlnumber
sed "s|@DIR@|$OUT|g" "$HERE/ca.cnf.template" > ca.cnf

openssl genrsa -out ca.key 4096 2>/dev/null
openssl req -x509 -new -key ca.key -sha256 -days 3650 -subj "/CN=iot-lab CA" -out ca.crt

openssl genrsa -out server.key 2048 2>/dev/null
openssl req -new -key server.key -subj "/CN=localhost" -out server.csr
openssl ca -batch -config ca.cnf -cert ca.crt -keyfile ca.key -extensions server_ext \
  -in server.csr -out server.crt -notext 2>/dev/null
rm -f server.csr

for name in "${GATEWAYS[@]}" "${MONITORS[@]}"; do
  openssl genrsa -out "devices/$name.key" 2048 2>/dev/null
  openssl req -new -key "devices/$name.key" -subj "/CN=$name" -out "devices/$name.csr"
  openssl ca -batch -config ca.cnf -cert ca.crt -keyfile ca.key -extensions device_ext \
    -in "devices/$name.csr" -out "devices/$name.crt" -notext 2>/dev/null
  rm -f "devices/$name.csr"
done

openssl ca -config ca.cnf -cert ca.crt -keyfile ca.key -gencrl -out crl.pem 2>/dev/null

: > acl
for name in "${GATEWAYS[@]}"; do
  cat >> acl <<ACL
user $name
topic write fabrik/+/+/temperatur
topic write fabrik/+/+/status
topic write fabrik/+/+/antal
topic write fabrik/+/+/gateway
topic read fabrik/+/+/kommando

ACL
done
for name in "${MONITORS[@]}"; do
  cat >> acl <<ACL
user $name
topic read fabrik/#
topic write fabrik/+/+/kommando

ACL
done

sed "s|@DIR@|$OUT|g" "$HERE/mosquitto.conf.template" > mosquitto.conf
chmod -R go-rwx .
