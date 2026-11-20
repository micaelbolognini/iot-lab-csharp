#!/usr/bin/env bash
# Usage: setup.sh OUTDIR  - creates CA, server cert, one client cert per device, OPC UA app certs, CRL, ACL and broker config.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
OUT=${1:?usage: setup.sh OUTDIR}
GATEWAYS=(gateway-py gateway-cs)
MONITORS=(monitor)
mkdir -p "$OUT"; OUT=$(cd "$OUT" && pwd); cd "$OUT"
umask 077
export OPCUA_APP=unused # openssl expands $ENV::OPCUA_APP while reading the whole config
mkdir -p newcerts devices opcua/trust opcua/crl opcua/pki/trusted/certs opcua/pki/trusted/crl
: > index.txt
echo 01 > serial
echo 01 > crlnumber
sed "s|@DIR@|$OUT|g" "$HERE/ca.cnf.template" > ca.cnf

openssl genrsa -out ca.key 4096 2>/dev/null
openssl req -x509 -new -key ca.key -sha256 -days 3650 -subj "/CN=iot-lab CA" \
  -addext "basicConstraints=critical,CA:TRUE" -addext "keyUsage=critical,keyCertSign,cRLSign" \
  -addext "subjectKeyIdentifier=hash" -out ca.crt

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

for name in machine "${GATEWAYS[@]}"; do
  openssl genrsa -out "opcua/$name.key" 2048 2>/dev/null
  openssl req -new -key "opcua/$name.key" -subj "/CN=$name" -out "opcua/$name.csr"
  OPCUA_APP=$name openssl ca -batch -config ca.cnf -cert ca.crt -keyfile ca.key -extensions opcua_ext \
    -in "opcua/$name.csr" -out "opcua/$name.crt" -notext 2>/dev/null
  rm -f "opcua/$name.csr"
done

openssl ca -config ca.cnf -cert ca.crt -keyfile ca.key -gencrl -out crl.pem 2>/dev/null

# asyncua's TrustStore scans directories for *.pem
ln -s ../../ca.crt opcua/trust/ca.pem
ln -s ../../crl.pem opcua/crl/crl.pem
# the OPC Foundation stack (C#) wants DER in certs/ and crl/
openssl x509 -in ca.crt -outform der -out opcua/pki/trusted/certs/ca.der
openssl crl -in crl.pem -outform der -out opcua/pki/trusted/crl/ca.crl

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
