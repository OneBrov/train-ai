namespace CoreSim.Simulation;

public sealed class SeededRandom : IRandom
{
    private readonly Random _random;

    public SeededRandom(int seed)
    {
        _random = new Random(seed);
    }

    public double NextDouble() => _random.NextDouble();
}
