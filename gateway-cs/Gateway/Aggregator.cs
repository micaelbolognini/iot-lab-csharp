namespace Gateway;

public class Aggregator
{
    private List<double> values;
    private readonly object gate = new();

    public Aggregator()
    {
        values = new List<double>();
    }

    public void Add(double value)
    {
        lock(gate){
            values.Add(value);
        }
    }

    public Summary? Summarize()
    {
        lock(gate){
            if (values.Count == 0)
                return null;

            var min = values.Min();
            var max = values.Max();
            var avg = values.Average();
            var n = values.Count;

            values.Clear();
            return new Summary(min, max, avg, n);
        }
    }

}
public record Summary(double Min, double Max, double Avg, int N);


