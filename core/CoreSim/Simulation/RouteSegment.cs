namespace CoreSim.Simulation;

public sealed class RouteSegment
{
    public RouteSegment(string name, double distanceKm, double roughness, double wearLevel = 0)
    {
        if (string.IsNullOrWhiteSpace(name)) throw new ArgumentException("Segment name is required.", nameof(name));
        if (distanceKm <= 0) throw new ArgumentOutOfRangeException(nameof(distanceKm));
        if (roughness < 0 || roughness > 1) throw new ArgumentOutOfRangeException(nameof(roughness));
        if (wearLevel < 0 || wearLevel > 1) throw new ArgumentOutOfRangeException(nameof(wearLevel));

        Name = name;
        DistanceKm = distanceKm;
        Roughness = roughness;
        WearLevel = wearLevel;
    }

    public string Name { get; }
    public double DistanceKm { get; }
    public double Roughness { get; }
    public double WearLevel { get; private set; }

    public double Quality => 1 - WearLevel;

    public double EffectiveRoughness => Math.Clamp(Roughness + WearLevel * 0.6, 0, 1);

    public void Degrade(double amount)
    {
        if (amount < 0) throw new ArgumentOutOfRangeException(nameof(amount));
        WearLevel = Math.Clamp(WearLevel + amount, 0, 1);
    }

    public void Maintain(double amount)
    {
        if (amount < 0) throw new ArgumentOutOfRangeException(nameof(amount));
        WearLevel = Math.Clamp(WearLevel - amount, 0, 1);
    }
}
