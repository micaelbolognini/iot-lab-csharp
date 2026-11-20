# IoT-labb: OPC UA → Edge → MQTT → C#

```
 [Maskin3]  ──OPC UA──▶  [Edge-gateway]  ──MQTT──▶  [Mosquitto]  ──▶  [Monitor, C#]
 machine/server.py       gateway/gateway.py          broker            monitor/
 (simulerad PLC)         aggregerar, buffrar,                          larmar, skickar
                         Last Will, kommandon   ◀────── "stop" ◀────── stop vid överhettning
```

Java-versionen av gatewayen bor i ett eget repo: `../iot-gateway-java`.

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

## Steg 2 — OPC UA: utforska maskinen (10 min)

```bash
# Flik 4: starta maskinen
.venv/bin/python machine/server.py

# Browsa adressrymden (asyncua har CLI-verktyg)
.venv/bin/uals -u opc.tcp://localhost:4840/iot-lab/ -l 3 -p 0:Objects
.venv/bin/uals -u opc.tcp://localhost:4840/iot-lab/ -p 0:Objects,2:Fabrik,2:Hall1,2:Maskin3

# Läs, skriv, anropa metod, prenumerera
.venv/bin/uaread -u opc.tcp://localhost:4840/iot-lab/ -p 0:Objects,2:Fabrik,2:Hall1,2:Maskin3,2:Temperatur
.venv/bin/uacall -u opc.tcp://localhost:4840/iot-lab/ -n "ns=2;i=3" -m "2:Start"   # Maskin3 = ns=2;i=3 (se uals)
.venv/bin/uaread -u opc.tcp://localhost:4840/iot-lab/ -n "ns=2;i=6"                 # Status, nu Running
.venv/bin/uasubscribe -u opc.tcp://localhost:4840/iot-lab/ -p 0:Objects,2:Fabrik,2:Hall1,2:Maskin3,2:Temperatur
```

Grafiskt: ladda ner **UaExpert** (gratis, Unified Automation) och anslut till `opc.tcp://localhost:4840/iot-lab/`.

Fundera: Varför är det värt något att klienten kan *browsa* och se typer, jämfört med MQTT där allt bara är bytes?

## Förberedelse — mTLS för steg 3 och 4

Steg 1 och 2 kör utan TLS. Från steg 3 körs brokern med mTLS: varje enhet har eget klientcert, och brokern nekar allt annat. Skapa certen en gång:

```bash
security/setup.sh security/generated   # CA, servercert, enhetscert, CRL, ACL, config
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

Gatewayn och monitorn får sina cert via `MQTT_CA`, `MQTT_CERT` och `MQTT_KEY`. Ett cert per enhet finns i `security/generated/devices/`: `gateway-py`, `gateway-cs`, `gateway-java` och `monitor`.

## Steg 3 — Edge-gatewayn (15 min)

Broker med mTLS (flik 1) och maskin (flik 4) igång.

```bash
msub -t 'fabrik/#' -v                                # flik 2
MQTT_CERT=$D/devices/gateway-py.crt MQTT_KEY=$D/devices/gateway-py.key \
  .venv/bin/python gateway/gateway.py                # flik 3
mpub -t fabrik/hall1/maskin3/kommando -m start       # någon flik
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

## Steg 5 — Egna övningar (skriv test först!)

1. **Hysteres:** monitorn skickar `stop` varje gång tills temperaturen sjunkit. Larma bara en gång tills den varit under gränsen igen. (Test i `TelemetryRulesTests.cs` först.)
2. **Fler maskiner:** starta en Maskin4 i servern. Monitorn hanterar den utan ändring tack vare `fabrik/+/+/temperatur` — varför?
3. **Deadband i gatewayn:** skicka `antal` högst en gång per sekund i stället för vid varje ändring.
4. **Spara historik:** låt monitorn skriva till SQLite (`Microsoft.Data.Sqlite`) och visa senaste timmens snitt.
5. **Spärra ett cert:** `security/revoke.sh security/generated gateway-cs`, starta om brokern och kolla att `gateway-cs` nekas medan de andra fortfarande ansluter. Tester: `.venv/bin/pytest security`.
6. **Ren nedstängning:** gatewayn ska publicera `offline` själv vid Ctrl+C (skillnad mot Last Will?).
7. **Sparkplug B:** läs om standarden — vilka av gatewayns topics/payloads skulle se annorlunda ut?

## Lärdomar

| Begrepp | Var i labbet |
|---|---|
| Pub/sub, broker, topic, wildcard | steg 1 |
| QoS 0/1/2, retained, Last Will | steg 1, 3 |
| OPC UA adressrymd, noder, browse, metoder, subscription | steg 2 |
| Edge: aggregering, store-and-forward | steg 3 |
| IT/OT, kommandon nedåt, sluten loop | steg 3, 4 |
| TLS, egen CA, mTLS, klientcert per enhet | `security/` |
| ACL per enhet, spärra ett cert med CRL | `security/` |
| Unified Namespace (topic-trädet fabrik/hall/maskin) | hela labbet |
