using System.Text.Json;

namespace Gateway;

public static class Payload
{
    public static string Temperature(Summary summary, DateTimeOffset ts)
    {
        
        return JsonSerializer.Serialize(new { 
            min = Math.Round(summary.Min,2),
            max = Math.Round(summary.Max,2),
            avg = Math.Round(summary.Avg, 2),
            n = summary.N,
            unit = "C",
            ts = ts.ToUnixTimeSeconds(),
        });
    }
}