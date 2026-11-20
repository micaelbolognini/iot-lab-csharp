namespace Gateway;

// TrustPath is an OPC UA trusted store: certs/ca.der and crl/ca.crl (see security/setup.sh)

public record OpcUaSettings(string Url, string App, string CertPath, string KeyPath, string TrustPath)
{
    public string ApplicationUri => $"urn:iot-lab:{App}";

    public static OpcUaSettings From(Func<string, string?> env)
    {
        string Required(string key) =>
            string.IsNullOrEmpty(env(key))
                ? throw new InvalidOperationException($"{key} must be set (encrypted OPC UA with client certificates is mandatory)")
                : env(key)!;

        return new OpcUaSettings(
            env("OPCUA_URL") ?? "opc.tcp://localhost:4840/iot-lab/",
            env("OPCUA_APP") ?? "gateway-cs",
            Required("OPCUA_CERT"),
            Required("OPCUA_KEY"),
            Required("OPCUA_TRUST"));
    }
}
