using Gateway;

public class AggregatorConcurrencyTests
{
    [Fact]
    public async Task Concurrent_adds_are_not_lost()
    {
        var aggregator = new Aggregator();

        // 8 trådar lägger till 10 000 värden var, samtidigt
        var tasks = Enumerable.Range(0, 8).Select(_ => Task.Run(() =>
        {
            for (var i = 0; i < 10_000; i++) aggregator.Add(1.0);
        }));
        await Task.WhenAll(tasks);   // ≈ Promise.all

        Assert.Equal(80_000, aggregator.Summarize()!.N);
    }
}