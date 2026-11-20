using Gateway;

public class MessageBufferTests
{
    [Fact]
    public void Sends_in_order_while_connection_works()
    {
        var buffer = new MessageBuffer<string>(maxLength: 10);
        buffer.Push("a");
        buffer.Push("b");
        var sent = new List<string>();

        buffer.Drain(msg => { sent.Add(msg); return true; });

        Assert.Equal(["a", "b"], sent);
        Assert.Equal(0, buffer.Count);
    }

    [Fact]
    public void Keeps_messages_when_send_fails()
    {
        var buffer = new MessageBuffer<string>(maxLength: 10);
        buffer.Push("a");
        buffer.Push("b");
        var sent = new List<string>();

        buffer.Drain(msg => { sent.Add(msg); return false; });

        Assert.Equal(["a"], sent);
        Assert.Equal(2, buffer.Count);  
    }

    [Fact]
    public void Drops_oldest_when_full()
    {
        var buffer = new MessageBuffer<string>(maxLength: 3);
        buffer.Push("a");
        buffer.Push("b");
        buffer.Push("c");
        buffer.Push("d"); // "a" ska bort

        var sent = new List<string>();
        buffer.Drain(msg => { sent.Add(msg); return true; });

        Assert.Equal(["b", "c", "d"], sent);
    }

    [Fact]
    public async Task DrainAsync_stops_at_first_failure_and_keeps_rest()
    {
        var buffer = new MessageBuffer<string>(10);
        buffer.Push("a");
        buffer.Push("b");
        buffer.Push("c");
        var sent = new List<string>();

        await buffer.DrainAsync(async item =>
        {
            await Task.Yield();             // låtsas vara nätverk
            if (item == "b") return false;  // brokern dog mitt i
            sent.Add(item);
            return true;
        });

        Assert.Equal(["a"], sent);
        Assert.Equal(2, buffer.Count);      // b och c kvar
    }
}