namespace Gateway;

public record MqttSettings(string Host, int Port, string CaPath, string CertPath, string KeyPath)
{
    public static MqttSettings From(Func<string, string?> env)
    {
        string Required(string key) =>
            string.IsNullOrEmpty(env(key))
                ? throw new InvalidOperationException($"{key} måste vara satt (TLS och klientcertifikat är obligatoriskt)")
                : env(key)!;

        return new MqttSettings(
            env("MQTT_HOST") ?? "localhost",
            int.Parse(env("MQTT_PORT") ?? "8883"),
            Required("MQTT_CA"),
            Required("MQTT_CERT"),
            Required("MQTT_KEY"));
    }
}
