using System.Security.Cryptography.X509Certificates;
using System.Text;
using Gateway;
using MQTTnet;
using MQTTnet.Client;
using MQTTnet.Protocol;
using MQTTnet.Exceptions;

const string Base = "fabrik/hall1/maskin3";

var aggregator = new Aggregator();
var guard = new OverheatGuard(28.0);
var buffer = new MessageBuffer<string>(1000);
// Ctrl+C → avbryt alla Task.Delay via token (≈ AbortController i JS)
using var cts = new CancellationTokenSource();
Console.CancelKeyPress += (_, e) => { e.Cancel = true; cts.Cancel(); };
await using var machine = new OpcUaMachine();
await machine.ConnectAsync("opc.tcp://localhost:4840/iot-lab/", cts.Token);
Console.WriteLine("OPC UA: ansluten till Maskin3");

var settings = MqttSettings.From(Environment.GetEnvironmentVariable);
var client = new MqttFactory().CreateMqttClient();
var options = new MqttClientOptionsBuilder()
    .WithTcpServer(settings.Host, settings.Port)
    .WithClientId("gateway-maskin3-cs")
    .WithTlsOptions(o => o
        .UseTls()
        .WithClientCertificates(new[] { X509Certificate2.CreateFromPemFile(settings.CertPath, settings.KeyPath) })
        .WithTrustChain(new X509Certificate2Collection(new X509Certificate2(settings.CaPath))))
    .WithWillTopic($"{Base}/gateway")      // Last Will: brokern skickar "offline" om vi dör
    .WithWillPayload("offline")
    .WithWillRetain()
    .Build();

client.ApplicationMessageReceivedAsync += async e =>
{
    var payload = Encoding.UTF8.GetString(e.ApplicationMessage.PayloadSegment);
    switch (Command.Parse(payload))
    {
        case MachineCommand.Start:
            await machine.StartAsync(cts.Token);
            Console.WriteLine("Kommando: start");
            break;
        case MachineCommand.Stop:
            await machine.StopAsync(cts.Token);
            Console.WriteLine("Kommando: stop");
            break;
        default:
            Console.WriteLine($"Okänt kommando: {payload}");
            break;
    }
};

await client.ConnectAsync(options, cts.Token);
await client.SubscribeAsync($"{Base}/kommando");
await client.PublishStringAsync($"{Base}/gateway", "online", retain: true);
Console.WriteLine("Gateway igång. Ctrl+C avslutar.");

await machine.OnTemperatureAsync(temp =>
{
    aggregator.Add(temp);
    if (guard.ShouldStop(temp))
    {
        Console.WriteLine($"EDGE: överhettning {temp:F1} °C, stoppar maskin3");
        _ = machine.StopAsync(CancellationToken.None);
    }
}, cts.Token);

// Huvudloop: var 5:e s → summera → publicera
try
{
    while (true)
    {
        await Task.Delay(TimeSpan.FromSeconds(5), cts.Token);
        var summary = aggregator.Summarize();
        if (summary is null) continue;

        buffer.Push(Payload.Temperature(summary, DateTimeOffset.UtcNow));

        if (!client.IsConnected)
        {
            try
            {
                await client.ConnectAsync(options, cts.Token);
                await client.SubscribeAsync($"{Base}/kommando");
                await client.PublishStringAsync($"{Base}/gateway", "online", retain: true);
                Console.WriteLine("Broker tillbaka, återansluten");
            }
            catch (MqttCommunicationException)
            {
                Console.WriteLine($"Broker nere, {buffer.Count} meddelanden buffrade");
                continue;
            }
        }

        await buffer.DrainAsync(async json =>
        {
            try
            {
                await client.PublishStringAsync($"{Base}/temperatur", json, MqttQualityOfServiceLevel.AtLeastOnce);
                Console.WriteLine($"{DateTime.Now:HH:mm:ss} {json}");
                return true;
            }
            catch (MqttCommunicationException)
            {
                return false;
            }
        });
    }
}
catch (OperationCanceledException) { }

// Ren nedstängning: säg "offline" själva (Last Will används bara vid krasch)

if (client.IsConnected)
{
    await client.PublishStringAsync($"{Base}/gateway", "offline", retain: true);
    await client.DisconnectAsync();
}
Console.WriteLine("Avslutad.");