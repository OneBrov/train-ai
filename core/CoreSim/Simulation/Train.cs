namespace CoreSim.Simulation;

public sealed class Train
{
    private readonly List<TrainPart> _parts = [];

    public Train(string name, double baseSpeed, double maxDurability, double baseCargoCapacity, double baseFuelPerKilometer)
    {
        if (string.IsNullOrWhiteSpace(name)) throw new ArgumentException("Train name is required.", nameof(name));
        if (baseSpeed <= 0) throw new ArgumentOutOfRangeException(nameof(baseSpeed));
        if (maxDurability <= 0) throw new ArgumentOutOfRangeException(nameof(maxDurability));
        if (baseCargoCapacity < 0) throw new ArgumentOutOfRangeException(nameof(baseCargoCapacity));
        if (baseFuelPerKilometer <= 0) throw new ArgumentOutOfRangeException(nameof(baseFuelPerKilometer));

        Name = name;
        BaseSpeed = baseSpeed;
        BaseMaxDurability = maxDurability;
        BaseCargoCapacity = baseCargoCapacity;
        BaseFuelPerKilometer = baseFuelPerKilometer;

        CurrentDurability = MaxDurability;
        FuelLevel = 100;
    }

    public string Name { get; }
    public double BaseSpeed { get; }
    public double BaseMaxDurability { get; }
    public double BaseCargoCapacity { get; }
    public double BaseFuelPerKilometer { get; }
    public double CurrentDurability { get; private set; }
    public double FuelLevel { get; private set; }

    public IReadOnlyList<TrainPart> Parts => _parts;

    public double MaxDurability => BaseMaxDurability + _parts.Sum(part => part.DurabilityBoost);

    public double EffectiveSpeed => BaseSpeed * _parts.Aggregate(1.0, (value, part) => value * part.SpeedMultiplier);

    public double CargoCapacity => BaseCargoCapacity + _parts.Sum(part => part.CargoCapacityBoost);

    public double EffectiveFuelPerKilometer => BaseFuelPerKilometer * _parts.Aggregate(1.0, (value, part) => value * part.FuelEfficiencyMultiplier);

    public void AddPart(TrainPart part)
    {
        ArgumentNullException.ThrowIfNull(part);

        _parts.Add(part);
        CurrentDurability = Math.Min(CurrentDurability, MaxDurability);
    }

    public void ConsumeFuel(double amount)
    {
        if (amount < 0) throw new ArgumentOutOfRangeException(nameof(amount));
        FuelLevel = Math.Max(0, FuelLevel - amount);
    }

    public void RefuelToFull()
    {
        FuelLevel = 100;
    }

    public void ApplyDamage(double damage)
    {
        if (damage < 0) throw new ArgumentOutOfRangeException(nameof(damage));

        CurrentDurability = Math.Max(0, CurrentDurability - damage);
    }

    public void Repair(double amount)
    {
        if (amount < 0) throw new ArgumentOutOfRangeException(nameof(amount));

        CurrentDurability = Math.Min(MaxDurability, CurrentDurability + amount);
    }
}
