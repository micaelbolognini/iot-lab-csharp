using System.Globalization;
using System.Text.Json;

namespace Monitor;

public record Alarm(string Machine, string Message, bool StopMachine);

/// <summary>
/// Regler för telemetri från topics på formen fabrik/{hall}/{maskin}/{mätning}.
/// Ren logik utan MQTT, så den går att testa.
/// </summary>
public class TelemetryRules(double maxTemperature)
{
    private readonly HashSet<string> alarmed=[];
    public Alarm? Evaluate(string topic, string payload)
    {
        var parts = topic.Split('/');
        if (parts.Length != 4) return null;
        var (machine, metric) = (parts[2], parts[3]);

        return metric switch
        {
            "temperatur" => Temperature(machine, payload),
            "gateway" when payload == "offline" =>
                new Alarm(machine, "gateway offline, ingen data från maskinen", StopMachine: false),
            _ => null,
        };
    }

    private Alarm? Temperature(string machine, string payload)
    {
        double max;
        try
        {
            using var doc = JsonDocument.Parse(payload);
            max = doc.RootElement.GetProperty("max").GetDouble();
        }
        catch (Exception e) when (e is JsonException or KeyNotFoundException or InvalidOperationException)
        {
            return null; // trasigt meddelande ska inte krascha konsumenten
        }

        if (max <= maxTemperature) 
        {
            alarmed.Remove(machine); // återställ larmstatus om temperaturen gått ner
            return null; // inget larm, allt är normalt
        }
        
        if(!alarmed.Add(machine)) return null; // redan larmat, inget nytt
        var message = string.Create(CultureInfo.InvariantCulture,
            $"temperatur {max} °C över gränsen {maxTemperature} °C");
        return new Alarm(machine, message, StopMachine: true);
    }
}
