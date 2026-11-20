using Opc.Ua;
using Opc.Ua.Client;
using Opc.Ua.Configuration;

namespace Gateway;

/// <summary>
/// OPC UA-klient mot Maskin3 i machine/server.py.
/// Nod-id:n kommer från uals: Maskin3 = ns=2;i=3, Temperatur = i=4, Start = i=8, Stop = i=10.
/// </summary>
public sealed class OpcUaMachine : IAsyncDisposable
{
    private static readonly NodeId Machine = new(3u, 2);
    private static readonly NodeId Temperature = new(4u, 2);
    private static readonly NodeId Start = new(8u, 2);
    private static readonly NodeId Stop = new(10u, 2);

    private readonly ITelemetryContext telemetry = DefaultTelemetry.Create(_ => { });
    private ISession? session;

    public async Task ConnectAsync(string endpointUrl, CancellationToken ct)
    {
        // Klienten behöver ett eget certifikat, även utan kryptering. Skapas i bin/.../pki första gången.
        var app = new ApplicationInstance(telemetry) { ApplicationName = "Gateway", ApplicationType = ApplicationType.Client };
#pragma warning disable CS0618 // enklaste överlagringen, räcker för labbet
        var config = await app.Build("urn:iot-lab:gateway", "urn:iot-lab:gateway")
            .AsClient()
            .AddSecurityConfiguration("CN=Gateway", Path.Combine(AppContext.BaseDirectory, "pki"))
#pragma warning restore CS0618
            .SetAutoAcceptUntrustedCertificates(true) // labb: lita på alla servrar
            .CreateAsync(ct);
        await app.CheckApplicationInstanceCertificatesAsync(false, null, ct);

        var endpoint = await CoreClientUtils.SelectEndpointAsync(config, endpointUrl, false, telemetry, ct);
        session = await new DefaultSessionFactory(telemetry).CreateAsync(
            config, new ConfiguredEndpoint(null!, endpoint!), false, "gateway", 60_000, new UserIdentity(), default, ct);
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
