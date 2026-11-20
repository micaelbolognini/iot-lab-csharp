namespace Gateway;

public class MessageBuffer<T>
{
    private readonly int maxLength;
    private readonly Queue<T> queue;

    public MessageBuffer(int maxLength)
    {
        this.maxLength = maxLength;
        queue = new Queue<T>();
    }

    public void Push(T item)
    {
        if (queue.Count >= maxLength)
        {
            queue.Dequeue(); // ta bort äldsta om vi är fulla
        }
        queue.Enqueue(item);
    }

    public void Drain(Func<T, bool> send)
    {
        while (queue.Count > 0)
        {
            var item = queue.Peek();
            if (!send(item)) break; // skicka tills det inte går längre
            queue.Dequeue();
        }
    }
    
    public async Task DrainAsync(Func<T, Task<bool>> send)
    {
        while (queue.Count > 0)
        {
            var item = queue.Peek();
            if (!await send(item)) break; // skicka tills det inte går längre
            queue.Dequeue();
        }
    }

    public int Count => queue.Count;
}