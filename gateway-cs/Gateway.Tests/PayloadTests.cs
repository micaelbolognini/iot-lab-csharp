using System.Text.Json;
using Gateway;

public class PayloadTests
{
    [Fact]
    public void Temperature_payload_has_summary_unit_and_timestamp()
    {
        var summary = new Summary(21.0, 24.5, 22.756, 10);
        var ts = DateTimeOffset.FromUnixTimeSeconds(1762600000);

        var json = Payload.Temperature(summary, ts);

        using var doc = JsonDocument.Parse(json);
        var root = doc.RootElement;
        Assert.Equal(21.0, root.GetProperty("min").GetDouble());
        Assert.Equal(24.5, root.GetProperty("max").GetDouble());
        Assert.Equal(22.76, root.GetProperty("avg").GetDouble());   // avrundat till 2 decimaler
        Assert.Equal(10, root.GetProperty("n").GetInt32());
        Assert.Equal("C", root.GetProperty("unit").GetString());
        Assert.Equal(1762600000, root.GetProperty("ts").GetDouble());
    }
}