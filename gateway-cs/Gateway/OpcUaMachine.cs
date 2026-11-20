using System.Security.Cryptography.X509Certificates;
using Opc.Ua;
using Opc.Ua.Client;
using Opc.Ua.Configuration;

namespace Gateway;

/// <summary>
/// OPC UA-klient mot Maskin3 i machine/server.py.
/// Nod-id:n kommer från uals: Maskin3 = ns=2;i=3, Temperatur = i=4, Start = i=10, Stop = i=12.
/// </summary>
public sealed class OpcUaMachine : IAsyncDisposable
{
    private static readonly NodeId Machine = new(3u, 2);
    private static readonly NodeId Temperature = new(4u, 2);
    private static readonly NodeId Start = new(10u, 2);
    private static readonly NodeId Stop = new(12u, 2);

    private readonly ITelemetryContext telemetry = DefaultTelemetry.Create(_ => { });
    private ISession? session;

    public async Task ConnectAsync(OpcUaSettings settings, CancellationToken ct, string? pkiRoot = null)
    {
        var pki = pkiRoot ?? Path.Combine(AppContext.BaseDirectory, "pki");
        StagePki(settings, pki);

        var app = new ApplicationInstance(telemetry) { ApplicationName = settings.App, ApplicationType = ApplicationType.Client };
#pragma warning disable CS0618 // simplest overload, enough for the lab
        var config = await app.Build(settings.ApplicationUri, settings.ApplicationUri)
            .AsClient()
            .AddSecurityConfiguration($"CN={settings.App}", pki)
#pragma warning restore CS0618
            .CreateAsync(ct);
        config.SecurityConfiguration.SendCertificateChain = false; // asyncua parses a single DER certificate
        await app.CheckApplicationInstanceCertificatesAsync(false, null, ct);

        var endpoint = await CoreClientUtils.SelectEndpointAsync(config, settings.Url, true, telemetry, ct)
            ?? throw new InvalidOperationException($"No endpoint found at {settings.Url}");
        if (endpoint.SecurityPolicyUri != SecurityPolicies.Basic256Sha256 || endpoint.SecurityMode != MessageSecurityMode.SignAndEncrypt)
            throw new InvalidOperationException("The machine offers no Basic256Sha256 SignAndEncrypt endpoint");
        session = await new DefaultSessionFactory(telemetry).CreateAsync(
            config, new ConfiguredEndpoint(null!, endpoint), false, settings.App, 60_000, new UserIdentity(), default, ct);
    }

    // The stack reads its identity and trust from a directory store, so lay the issued PEM files out there.
    private static void StagePki(OpcUaSettings settings, string pki)
    {
        if (Directory.Exists(pki)) Directory.Delete(pki, true);
        var certs = Directory.CreateDirectory(Path.Combine(pki, "own", "certs")).FullName;
        var priv = Directory.CreateDirectory(Path.Combine(pki, "own", "private")).FullName;
        using var cert = X509Certificate2.CreateFromPemFile(settings.CertPath, settings.KeyPath);
        var name = $"{settings.App} [{cert.Thumbprint}]";
        File.WriteAllBytes(Path.Combine(certs, name + ".der"), cert.RawData);
        File.WriteAllBytes(Path.Combine(priv, name + ".pfx"), cert.Export(X509ContentType.Pfx));
        foreach (var sub in new[] { "certs", "crl" })
        {
            var target = Directory.CreateDirectory(Path.Combine(pki, "trusted", sub)).FullName;
            foreach (var file in Directory.GetFiles(Path.Combine(settings.TrustPath, sub)))
                File.Copy(file, Path.Combine(target, Path.GetFileName(file)));
        }
    }

    /// <summary>Servern pushar nya temperaturer (subscription), vi pollar inte.</summary>
    public async Task OnTemperatureAsync(Action<double> handler, CancellationToken ct)
    {
        var subscription = new Subscription(telemetry, new SubscriptionOptions
        {
            PublishingInterval = 500,
            PublishingEnabled = true,
            KeepAliveCount = 10,
            LifetimeCount = 100,
            SequentialPublishing = true, // en notifiering i taget, i ordning
        });
        var item = new MonitoredItem(telemetry, new MonitoredItemOptions { StartNodeId = Temperature, SamplingInterval = 500 });
        item.Notification += (_, e) =>
        {
            if (e.NotificationValue is MonitoredItemNotification n
                && n.Value.WrappedValue.TryGetValue(out double temperature))
                handler(temperature);
        };
        subscription.AddItem(item);
        session!.AddSubscription(subscription);
        await subscription.CreateAsync(ct);
    }

    public Task StartAsync(CancellationToken ct) => session!.CallAsync(Machine, Start, ct);
    public Task StopAsync(CancellationToken ct) => session!.CallAsync(Machine, Stop, ct);

    public async ValueTask DisposeAsync()
    {
        if (session is not null) await session.CloseAsync(5000, true, default);
    }
}
