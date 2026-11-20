using Gateway;

public class CommandTests
{
    [Theory]
    [InlineData("start", MachineCommand.Start)]
    [InlineData("stop", MachineCommand.Stop)]
    [InlineData(" STOP\n", MachineCommand.Stop)]   // slarvig input från mosquitto_pub
    public void Parses_known_commands(string payload, MachineCommand expected)
    {
        Assert.Equal(expected, Command.Parse(payload));
    }

    [Fact]
    public void Unknown_command_gives_null()
    {
        Assert.Null(Command.Parse("explode"));
    }
}


