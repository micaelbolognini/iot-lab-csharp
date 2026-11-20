namespace Gateway;

public class OverheatGuard(double maxTemperature)
{
    private bool stopped;   // har vi redan stoppat?

    public bool ShouldStop(double temperature)
    {
        if (temperature <= maxTemperature)
        {
            stopped = false;
            return stopped;
        }

        if (stopped)
        {
            return false;
        }

        
        stopped = true;
        return stopped;
        
    }
}
