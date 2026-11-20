using Gateway;

public class OverheatGuardTests
{
    [Fact]
    public void Should_stop_when_overheated()
    {
        var guard = new OverheatGuard(maxTemperature: 80);
        Assert.True(guard.ShouldStop(90)); // Överhettning
    }

    [Fact]
    public void Should_not_stop_when_normal()
    {
        var guard = new OverheatGuard(maxTemperature: 80);
        Assert.False(guard.ShouldStop(20));
    }

    [Fact]
    public void Does_not_stop_again_while_still_overheated()
    {
        var guard = new OverheatGuard(maxTemperature: 80);
        Assert.True(guard.ShouldStop(90));
        Assert.False(guard.ShouldStop(99));
    }

    [Fact]
    public void Stops_again_after_cooling_down()
    {
        var guard = new OverheatGuard(maxTemperature: 80);
        guard.ShouldStop(90);   // stopp
        guard.ShouldStop(70);   // svalnat
        Assert.True(guard.ShouldStop(95));   // varm igen → nytt stopp
    }
}