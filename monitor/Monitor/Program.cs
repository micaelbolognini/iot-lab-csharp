// Konsument "i molnet": prenumererar på hela fabriken, larmar och stoppar maskiner som blir för varma.
using System.Security.Cryptography.X509Certificates;
using System.Text;
using Monitor;
using MQTTnet;
using MQTTnet.Client;

var maxTemperature = args.Length > 0 ? double.Parse(args[0], System.Globalization.CultureInfo.InvariantCulture) : 30.0;
var rules = new TelemetryRules(maxTemperature);

var settings = MqttSettings.From(Environment.GetEnvironmentVariable);
var client = new MqttFactory().CreateMqttClient();
var options = new MqttClientOptionsBuilder()
    .WithTcpServer(settings.Host, settings.Port)
    .WithClientId("monitor")
    .WithTlsOptions(o => o
        .UseTls()
        .WithClientCertificates(new[] { X509Certificate2.CreateFromPemFile(settings.CertPath, settings.KeyPath) })
        .WithTrustChain(new X509Certificate2Collection(new X509Certificate2(settings.CaPath))))
    .Build();

client.ApplicationMessageReceivedAsync += async e =>
{
    var topic = e.ApplicationMessage.Topic;
    var payload = Encoding.UTF8.GetString(e.ApplicationMessage.PayloadSegment);
    Console.WriteLine($"{DateTime.Now:HH:mm:ss} {topic} {payload}");

    var alarm = rules.Evaluate(topic, payload);
    if (alarm is null) return;

    Console.ForegroundColor = ConsoleColor.Red;
    Console.WriteLine($"  LARM {alarm.Machine}: {alarm.Message}");
    Console.ResetColor();

    if (alarm.StopMachine)
    {
        var hall = topic.Split('/')[1];
        await client.PublishStringAsync($"fabrik/{hall}/{alarm.Machine}/kommando", "stop");
        Console.WriteLine($"  -> skickade stop till {alarm.Machine}");
    }
};

await client.ConnectAsync(options);
await client.SubscribeAsync("fabrik/+/+/temperatur");
await client.SubscribeAsync("fabrik/+/+/gateway");
Console.WriteLine($"Monitor igång, larmgräns {maxTemperature} °C. Ctrl+C avslutar.");

var done = new TaskCompletionSource();
Console.CancelKeyPress += (_, e) => { e.Cancel = true; done.TrySetResult(); };
await done.Task;
await client.DisconnectAsync();
