import os
from dataclasses import dataclass
from pathlib import Path

from asyncua import Client, ua
from asyncua.crypto import security_policies
from asyncua.crypto.truststore import TrustStore
from asyncua.crypto.uacrypto import CertProperties
from asyncua.crypto.validator import CertificateValidator, CertificateValidatorOptions


@dataclass(frozen=True)
class OpcUaSettings:
    url: str
    app: str
    cert: str
    key: str
    trust: str
    crl: str


def opcua_settings(env=os.environ):
    for key in ("OPCUA_CERT", "OPCUA_KEY", "OPCUA_TRUST", "OPCUA_CRL"):
        if not env.get(key):
            raise ValueError(f"{key} must be set (encrypted OPC UA with client certificates is mandatory)")
    return OpcUaSettings(
        url=env.get("OPCUA_URL", "opc.tcp://localhost:4840/iot-lab/"),
        app=env.get("OPCUA_APP", "gateway-py"),
        cert=env["OPCUA_CERT"],
        key=env["OPCUA_KEY"],
        trust=env["OPCUA_TRUST"],
        crl=env["OPCUA_CRL"],
    )


async def secure_client(settings):
    client = Client(settings.url)
    client.application_uri = f"urn:iot-lab:{settings.app}"
    store = TrustStore([Path(settings.trust)], [Path(settings.crl)])
    await store.load()
    options = CertificateValidatorOptions.TRUSTED_VALIDATION | CertificateValidatorOptions.PEER_SERVER
    client.certificate_validator = CertificateValidator(options, store).validate
    await client.set_security(
        security_policies.SecurityPolicyBasic256Sha256,
        CertProperties(settings.cert, "pem"),
        CertProperties(settings.key, "pem"),
        mode=ua.MessageSecurityMode.SignAndEncrypt,
    )
    return client
