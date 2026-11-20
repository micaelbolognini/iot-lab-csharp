using Monitor;
using Xunit;

namespace Monitor.Tests;

public class MqttSettingsTests
{
    private static readonly Dictionary<string, string?> Env = new()
    {
        ["MQTT_CA"] = "/x/ca.crt",
        ["MQTT_CERT"] = "/x/monitor.crt",
        ["MQTT_KEY"] = "/x/monitor.key",
    };

    private static string? Get(IDictionary<string, string?> env, string key) =>
        env.TryGetValue(key, out var v) ? v : null;

    [Fact]
    public void Defaults_to_tls_port_on_localhost()
    {
        var s = MqttSettings.From(k => Get(Env, k));

        Assert.Equal("localhost", s.Host);
        Assert.Equal(8883, s.Port);
        Assert.Equal("/x/ca.crt", s.CaPath);
        Assert.Equal("/x/monitor.crt", s.CertPath);
        Assert.Equal("/x/monitor.key", s.KeyPath);
    }

    [Fact]
    public void Host_and_port_can_be_overridden()
    {
        var env = new Dictionary<string, string?>(Env) { ["MQTT_HOST"] = "gizmo", ["MQTT_PORT"] = "9000" };

        var s = MqttSettings.From(k => Get(env, k));

        Assert.Equal(("gizmo", 9000), (s.Host, s.Port));
    }

    [Theory]
    [InlineData("MQTT_CA")]
    [InlineData("MQTT_CERT")]
    [InlineData("MQTT_KEY")]
    public void Refuses_to_run_without_tls_and_client_certificate(string missing)
    {
        var env = new Dictionary<string, string?>(Env);
        env.Remove(missing);

        var ex = Assert.Throws<InvalidOperationException>(() => MqttSettings.From(k => Get(env, k)));

        Assert.Contains(missing, ex.Message);
    }
}
