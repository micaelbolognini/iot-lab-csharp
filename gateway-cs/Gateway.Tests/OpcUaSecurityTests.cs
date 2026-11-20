using System.Diagnostics;
using System.Net.Sockets;
using Gateway;
using Xunit;

namespace Gateway.Tests;

// Needs bash, openssl and a python with asyncua (IOT_LAB_PYTHON or <repo>/.venv). Skips itself if it has none.
public class OpcUaSecurityTests : IDisposable
{
    private readonly string work = Directory.CreateTempSubdirectory("opcua-").FullName;
    private readonly List<Process> machines = new();

    public void Dispose()
    {
        foreach (var m in machines) { m.Kill(true); m.WaitForExit(); }
        Directory.Delete(work, true);
    }

    private static string Repo()
    {
        var dir = new DirectoryInfo(AppContext.BaseDirectory);
        while (dir is not null && !File.Exists(Path.Combine(dir.FullName, "security", "setup.sh"))) dir = dir.Parent;
        return dir?.FullName ?? throw new InvalidOperationException("repo root not found");
    }

    private static string? Python(string repo)
    {
        var configured = Environment.GetEnvironmentVariable("IOT_LAB_PYTHON");
        if (!string.IsNullOrEmpty(configured)) return configured;
        var venv = Path.Combine(repo, ".venv", "bin", "python");
        return File.Exists(venv) ? venv : null;
    }

    private static void Run(string file, params string[] args)
    {
        var p = Process.Start(new ProcessStartInfo(file, args) { RedirectStandardError = true })!;
        var error = p.StandardError.ReadToEnd();
        p.WaitForExit();
        Assert.True(p.ExitCode == 0, error);
    }

    private string MakePki(string name)
    {
        var pki = Path.Combine(work, name);
        Run(Path.Combine(Repo(), "security", "setup.sh"), pki);
        return pki;
    }

    private void StartMachine(string pki, string python, int port)
    {
        var info = new ProcessStartInfo(python, Path.Combine(Repo(), "machine", "server.py")) { RedirectStandardError = true };
        info.Environment["OPCUA_PORT"] = port.ToString();
        info.Environment["OPCUA_CERT"] = Path.Combine(pki, "opcua", "machine.crt");
        info.Environment["OPCUA_KEY"] = Path.Combine(pki, "opcua", "machine.key");
        info.Environment["OPCUA_TRUST"] = Path.Combine(pki, "opcua", "trust");
        info.Environment["OPCUA_CRL"] = Path.Combine(pki, "opcua", "crl");
        var machine = Process.Start(info)!;
        machines.Add(machine);
        for (var i = 0; i < 100; i++)
        {
            if (machine.HasExited) throw new InvalidOperationException(machine.StandardError.ReadToEnd());
            try { using var c = new TcpClient("127.0.0.1", port); return; } catch (SocketException) { Thread.Sleep(100); }
        }
        throw new TimeoutException("machine did not start");
    }

    private static OpcUaSettings Settings(string clientPki, string trustPki, int port) => new(
        $"opc.tcp://localhost:{port}/iot-lab/", "gateway-cs",
        Path.Combine(clientPki, "opcua", "gateway-cs.crt"), Path.Combine(clientPki, "opcua", "gateway-cs.key"),
        Path.Combine(trustPki, "opcua", "pki", "trusted"));

    private static async Task<double> ReadTemperature(OpcUaSettings settings, string pkiRoot)
    {
        await using var machine = new OpcUaMachine();
        await machine.ConnectAsync(settings, CancellationToken.None, pkiRoot);
        var value = new TaskCompletionSource<double>();
        await machine.OnTemperatureAsync(v => value.TrySetResult(v), CancellationToken.None);
        return await value.Task.WaitAsync(TimeSpan.FromSeconds(10));
    }

    [Fact]
    public async Task Reads_temperature_over_encrypted_channel_with_trusted_certificates()
    {
        var python = Python(Repo());
        if (python is null) return;
        var pki = MakePki("pki");
        StartMachine(pki, python, 14871);

        var temperature = await ReadTemperature(Settings(pki, pki, 14871), Path.Combine(work, "client-pki"));

        Assert.InRange(temperature, -50, 150);
    }

    [Fact]
    public async Task Refuses_a_machine_whose_certificate_comes_from_another_ca()
    {
        var python = Python(Repo());
        if (python is null) return;
        var pki = MakePki("pki");
        var foreign = MakePki("foreign");
        // The machine trusts our gateway but presents a certificate from a CA we do not trust.
        var rogue = Path.Combine(work, "rogue");
        Directory.CreateDirectory(Path.Combine(rogue, "opcua"));
        foreach (var f in new[] { "machine.crt", "machine.key" })
            File.Copy(Path.Combine(foreign, "opcua", f), Path.Combine(rogue, "opcua", f));
        Directory.CreateSymbolicLink(Path.Combine(rogue, "opcua", "trust"), Path.Combine(pki, "opcua", "trust"));
        Directory.CreateSymbolicLink(Path.Combine(rogue, "opcua", "crl"), Path.Combine(pki, "opcua", "crl"));
        StartMachine(rogue, python, 14872);

        await Assert.ThrowsAnyAsync<Exception>(() =>
            ReadTemperature(Settings(pki, pki, 14872), Path.Combine(work, "client-pki")));
    }
}
