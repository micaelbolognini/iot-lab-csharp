using Monitor;

public class TelemetryRulesTests
{
    private readonly TelemetryRules rules = new(maxTemperature: 30.0);

    [Fact]
    public void Overheating_raises_alarm_and_stops_machine()
    {
        var alarm = rules.Evaluate("fabrik/hall1/maskin3/temperatur",
            """{"min": 28.1, "max": 31.4, "avg": 29.9, "n": 10, "unit": "C"}""");

        Assert.NotNull(alarm);
        Assert.Equal("maskin3", alarm.Machine);
        Assert.Equal("temperatur 31.4 °C över gränsen 30 °C", alarm.Message);
        Assert.True(alarm.StopMachine);
    }

    [Fact]
    public void Normal_temperature_gives_no_alarm()
    {
        Assert.Null(rules.Evaluate("fabrik/hall1/maskin3/temperatur",
            """{"min": 20.0, "max": 24.0, "avg": 22.0, "n": 10}"""));
    }

    [Fact]
    public void Gateway_offline_raises_alarm_without_stopping()
    {
        var alarm = rules.Evaluate("fabrik/hall1/maskin3/gateway", "offline");

        Assert.NotNull(alarm);
        Assert.Equal("gateway offline, ingen data från maskinen", alarm.Message);
        Assert.False(alarm.StopMachine);
    }

    [Fact]
    public void Broken_payload_is_ignored()
    {
        Assert.Null(rules.Evaluate("fabrik/hall1/maskin3/temperatur", "inte json"));
    }

    [Fact]
    public void Other_topics_are_ignored()
    {
        Assert.Null(rules.Evaluate("fabrik/hall1/maskin3/antal", """{"value": 5}"""));
    }
    [Fact]
    public void Continued_overheating_raises_only_one_alarm()
    {
        var first = rules.Evaluate("fabrik/hall1/maskin3/temperatur",
            """{"min": 28.1, "max": 31.4, "avg": 29.9, "n": 10, "unit": "C"}""");

        var second = rules.Evaluate("fabrik/hall1/maskin3/temperatur",
            """{"min": 28.1, "max": 32.4, "avg": 29.9, "n": 10, "unit": "C"}""");

        Assert.NotNull(first);
        Assert.Null(second);   // redan larmat, inget nytt
    }

    [Fact]
    public void Alarm_resets_when_temperature_drops_below_limit()
    {
        rules.Evaluate("fabrik/hall1/maskin3/temperatur", """{"max": 31.4}""");   // larm
        rules.Evaluate("fabrik/hall1/maskin3/temperatur", """{"max": 25.0}""");   // svalnat

        var again = rules.Evaluate("fabrik/hall1/maskin3/temperatur", """{"max": 33.0}""");

        Assert.NotNull(again);
    }
}
