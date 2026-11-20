namespace Gateway;

public enum MachineCommand { Start, Stop }

public static class Command
{
    public static MachineCommand? Parse(string payload)
    {
        var clean = payload.Trim().ToLowerInvariant(); 
        return clean switch
        {
            "start" => MachineCommand.Start,
            "stop" => MachineCommand.Stop,
            _ => null,
        };
    }
}