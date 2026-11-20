using Gateway;

public class AggregatorTests
{
    [Fact]
    public void Summarizes_values_and_resets()
    {
        var agg = new Aggregator();
        foreach (var v in new[] { 20.0, 22.0, 24.0 })
        {
            agg.Add(v);
        }

        Assert.Equal(new Summary(20.0, 24.0, 22.0, 3), agg.Summarize());
        Assert.Null(agg.Summarize());   // tömd efter summering
    }
}