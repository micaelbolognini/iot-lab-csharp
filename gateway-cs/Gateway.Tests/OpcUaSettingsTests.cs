using Gateway;
using Xunit;

namespace Gateway.Tests;

public class OpcUaSettingsTests
{
    private static readonly Dictionary<string, string?> Env = new()
    {
        ["OPCUA_CERT"] = "/x/gateway-cs.crt",
        ["OPCUA_KEY"] = "/x/gateway-cs.key",
        ["OPCUA_TRUST"] = "/x/trust",
    };

    private static string? Get(IDictionary<string, string?> env, string key) =>
        env.TryGetValue(key, out var v) ? v : null;

    [Fact]
    public void Defaults_to_local_machine_and_csharp_gateway_identity()
    {
        var s = OpcUaSettings.From(k => Get(Env, k));

        Assert.Equal("opc.tcp://localhost:4840/iot-lab/", s.Url);
        Assert.Equal("gateway-cs", s.App);
        Assert.Equal("urn:iot-lab:gateway-cs", s.ApplicationUri);
        Assert.Equal(("/x/gateway-cs.crt", "/x/gateway-cs.key"), (s.CertPath, s.KeyPath));
        Assert.Equal("/x/trust", s.TrustPath);
    }

    [Fact]
    public void Url_and_app_can_be_overridden()
    {
        var env = new Dictionary<string, string?>(Env) { ["OPCUA_URL"] = "opc.tcp://plc:4840/x/", ["OPCUA_APP"] = "gateway-x" };

        var s = OpcUaSettings.From(k => Get(env, k));

        Assert.Equal(("opc.tcp://plc:4840/x/", "urn:iot-lab:gateway-x"), (s.Url, s.ApplicationUri));
    }

    [Theory]
    [InlineData("OPCUA_CERT")]
    [InlineData("OPCUA_KEY")]
    [InlineData("OPCUA_TRUST")]
    public void Refuses_to_run_without_opcua_certificates(string missing)
    {
        var env = new Dictionary<string, string?>(Env);
        env.Remove(missing);

        var ex = Assert.Throws<InvalidOperationException>(() => OpcUaSettings.From(k => Get(env, k)));

        Assert.Contains(missing, ex.Message);
    }
}
