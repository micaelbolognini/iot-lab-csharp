# IoT-labb: OPC UA → Edge → MQTT → C#

```
 [Maskin3]  ──OPC UA──▶  [Edge-gateway]  ──MQTT──▶  [Mosquitto]  ──▶  [Monitor, C#]
 machine/server.py       gateway/gateway.py          broker            monitor/
 (simulerad PLC)         aggregerar, buffrar,                          larmar, skickar
                         Last Will, kommandon   ◀────── "stop" ◀────── stop vid överhettning
```

Öppna fyra terminalflikar, alla i repots rot.

---

## Steg 1 — MQTT för hand (10 min)

```bash
# Flik 1: broker
mosquitto -v

# Flik 2: prenumerera på allt under fabrik
mosquitto_sub -t 'fabrik/#' -v

# Flik 3: publicera
mosquitto_pub -t fabrik/hall1/maskin1/temp -m 21.5
```

Prova:
- **Wildcards:** `mosquitto_sub -t 'fabrik/+/maskin1/#' -v` — vad matchar, vad matchar inte?
- **Retained:** `mosquitto_pub -t fabrik/hall1/maskin1/status -m Running -r`. Starta en NY sub efteråt. Den får värdet direkt. Utan `-r`?
- **Rensa retained:** `mosquitto_pub -t fabrik/hall1/maskin1/status -r -n`
- **QoS:** `-q 0`, `-q 1`, `-q 2` och kör brokern med `-v` och se skillnaden i paket (PUBACK, PUBREC/PUBREL/PUBCOMP).
- **Last Will:** `mosquitto_sub -t test -i x --will-topic dead/x --will-payload "borta"` och döda den med `kill -9`. Vad dyker upp på `dead/x`?

## Förberedelse — certifikat för steg 2–4

Steg 1 kör utan TLS. Från steg 2 kräver maskinen OPC UA med certifikat, och från steg 3 körs brokern med mTLS: varje enhet har eget klientcert, och brokern nekar allt annat. Skapa certen en gång:

```bash
security/setup.sh security/generated   # CA, servercert, enhetscert, OPC UA-cert, CRL, ACL, config
```

Gör i varje flik som behöver prata med brokern:

```bash
D=$PWD/security/generated
export MQTT_CA=$D/ca.crt
mpub() { mosquitto_pub -p 8883 --cafile "$D/ca.crt" --cert "$D/devices/monitor.crt" --key "$D/devices/monitor.key" "$@"; }
msub() { mosquitto_sub -p 8883 --cafile "$D/ca.crt" --cert "$D/devices/monitor.crt" --key "$D/devices/monitor.key" "$@"; }
```

`mpub` och `msub` är monitorns identitet, som får läsa allt och skicka kommandon. Brokern startas nu så här (flik 1):

```bash
mosquitto -c security/generated/mosquitto.conf
```

Gatewayn och monitorn får sina cert via `MQTT_CA`, `MQTT_CERT` och `MQTT_KEY`. Ett cert per enhet finns i `security/generated/devices/`: `gateway-py`, `gateway-cs` och `monitor`.

OPC UA-länken gateway → maskin har egna applikationscert i `security/generated/opcua/` (URI `urn:iot-lab:<namn>` i SAN). Python-gatewayn läser `OPCUA_CERT`, `OPCUA_KEY`, `OPCUA_TRUST` (`opcua/trust`) och `OPCUA_CRL` (`opcua/crl`). C#-gatewayn läser `OPCUA_CERT`, `OPCUA_KEY` och `OPCUA_TRUST` (`opcua/pki/trusted`, DER med CRL). Båda har valfria `OPCUA_URL` och `OPCUA_APP`. Maskinen litar bara på klientcert från CA:n och nekar spärrade (`security/revoke.sh generated opcua/gateway-cs`). Gatewayn kontrollerar i sin tur maskinens cert.

## Steg 2 — OPC UA och Ignition

Maskinen kräver krypterad OPC UA (`Basic256Sha256`, SignAndEncrypt) och klientcert utfärdade av labbets CA. Certen kommer från `security/setup.sh` i avsnittet "Förberedelse" ovan.

```bash
# Flik 4: starta maskinen
D=$PWD/security/generated
OPCUA_CERT=$D/opcua/machine.crt OPCUA_KEY=$D/opcua/machine.key \
  OPCUA_TRUST=$D/opcua/trust OPCUA_CRL=$D/opcua/crl .venv/bin/python machine/server.py
```

Maskinen är en OPC UA-server på `opc.tcp://localhost:4840/iot-lab/` med taggarna `Temperatur`, `Varvtal`, `Status` och `Antal`, plus de skrivbara `Borvarde` och `Kor`.

Koppla **Ignition** (Inductive Automation), ett stort grafiskt verktyg, mot den. Det här steget är manuellt och inte testat: Ignition behöver ett klientcert utfärdat av labbets CA (`security/setup.sh` skapar inget åt Ignition) och måste lita på maskinens cert.

1. Logga in i Gateway på `localhost:8088` och lägg till en OPC UA-klientanslutning (Connections) mot adressen ovan.
2. Browsa maskinens taggar i Designer.
3. Bygg en vy med en av/på-knapp mot den skrivbara taggen `Kor` och ett överhettningsskydd på `Temperatur`.

Fundera: Varför är det värt något att klienten kan *browsa* och se typer, jämfört med MQTT där allt bara är bytes?

## Steg 3 — Edge-gatewayn (15 min)

Broker med mTLS (flik 1) och maskin (flik 4) igång.

```bash
msub -t 'fabrik/#' -v                                # flik 2
MQTT_CERT=$D/devices/gateway-py.crt MQTT_KEY=$D/devices/gateway-py.key \
  OPCUA_CERT=$D/opcua/gateway-py.crt OPCUA_KEY=$D/opcua/gateway-py.key \
  OPCUA_TRUST=$D/opcua/trust OPCUA_CRL=$D/opcua/crl \
  .venv/bin/python gateway/gateway.py                # flik 3
mpub -t fabrik/hall1/maskin3/kommando -m start       # någon flik
```

C#-gatewayn kan köras i stället för Python-gatewayn. Den skickar `temperatur` och `gateway` och tar emot `kommando`, men publicerar inte `status` och `antal`:

```bash
MQTT_CERT=$D/devices/gateway-cs.crt MQTT_KEY=$D/devices/gateway-cs.key \
  OPCUA_CERT=$D/opcua/gateway-cs.crt OPCUA_KEY=$D/opcua/gateway-cs.key \
  OPCUA_TRUST=$D/opcua/pki/trusted \
  dotnet run --project gateway-cs/Gateway
```

Se i flik 2:
- `temperatur` kommer var 5:e sekund som min/max/avg, inte varje värde. **Edge-aggregering**.
- `status` och `antal` är retained.
- `gateway online`.

Experiment:
1. **Avbrott mot molnet:** stoppa brokern (Ctrl+C i flik 1) i 20 s och starta igen. Gatewayn buffrar (`Broker nere, N meddelanden buffrade`) och skickar ikapp. **Store-and-forward.**
2. **Gatewayn dör:** Ctrl+C i flik 3. Flik 2 visar `gateway offline` — brokern skickade Last Will.
3. **Kommandon nedåt:** `-m stop`. Moln → MQTT → gateway → OPC UA-metod → maskin.

## Steg 4 — C#-konsumenten (15 min)

```bash
dotnet test monitor                    # 12 tester
MQTT_CERT=$D/devices/monitor.crt MQTT_KEY=$D/devices/monitor.key \
  dotnet run --project monitor/Monitor -- 24     # larmgräns 24 °C
mpub -t fabrik/hall1/maskin3/kommando -m start
```

Maskinen värms upp, monitorn larmar och skickar `stop`. En sluten styrloop.

Läs `Monitor/TelemetryRules.cs` (logiken) och `Program.cs` (MQTTnet). Jämför med Laravel:
records ≈ DTO:er, `switch`-uttryck ≈ `match`, xUnit ≈ Pest.

## Tester och spärrning

```bash
.venv/bin/pytest security gateway      # Python: broker, OPC UA, config
dotnet test monitor
dotnet test gateway-cs                 # startar maskinen, behöver .venv eller IOT_LAB_PYTHON=<python med asyncua>
```

C#-integrationstesterna hoppar över sig själva om ingen Python med asyncua hittas.

Spärra ett cert med `security/revoke.sh security/generated gateway-cs` och starta om brokern. För OPC UA: `security/revoke.sh security/generated opcua/gateway-cs` och starta om maskinen, som läser CRL vid start.

## Lärdomar

| Begrepp | Var i labbet |
|---|---|
| Pub/sub, broker, topic, wildcard | steg 1 |
| QoS 0/1/2, retained, Last Will | steg 1, 3 |
| OPC UA adressrymd, noder, browse, metoder, subscription | steg 2 |
| Edge: aggregering, store-and-forward | steg 3 |
| IT/OT, kommandon nedåt, sluten loop | steg 3, 4 |
| TLS, egen CA, mTLS, klientcert per enhet | `security/` |
| OPC UA Basic256Sha256, applikationscert, trust list | `security/`, `machine/server.py` |
| ACL per enhet, spärra ett cert med CRL | `security/` |
| Unified Namespace (topic-trädet fabrik/hall/maskin) | hela labbet |
