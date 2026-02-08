namespace CoreSim.Simulation;

public sealed class SimulationEngine
{
    private readonly IRandom _random;

    public SimulationEngine(IRandom random)
    {
        _random = random ?? throw new ArgumentNullException(nameof(random));
    }

    public TripResult ExecuteTrip(Train train, TripRequest request)
    {
        ArgumentNullException.ThrowIfNull(train);
        ArgumentNullException.ThrowIfNull(request);

        if (request.CargoWeight < 0) throw new ArgumentOutOfRangeException(nameof(request.CargoWeight));
        if (request.CargoRatePerKm < 0) throw new ArgumentOutOfRangeException(nameof(request.CargoRatePerKm));

        if (request.CargoWeight > train.CargoCapacity)
        {
            return new TripResult(
                IsCompleted: false,
                RequiresRepair: false,
                RequiresRefuel: false,
                Revenue: 0,
                RepairCost: 0,
                FuelCost: 0,
                DistanceTravelled: 0,
                DamageTaken: 0,
                Events: ["Cargo is above train capacity."]);
        }

        var events = new List<string>();
        var fuelCost = 0m;
        var distanceTravelled = 0.0;
        var damageTaken = 0.0;

        foreach (var segment in request.Route.Segments)
        {
            var fuelRequired = segment.DistanceKm * train.EffectiveFuelPerKilometer;
            if (train.FuelLevel < fuelRequired)
            {
                events.Add($"Out of fuel near segment '{segment.Name}'.");
                break;
            }

            train.ConsumeFuel(fuelRequired);
            fuelCost += (decimal)fuelRequired * 1.8m;

            var rawDamage = segment.DistanceKm * segment.EffectiveRoughness * 0.28;
            var randomDamageFactor = 0.9 + (_random.NextDouble() * 0.25);
            var cargoDamageFactor = 1 + (request.CargoWeight / Math.Max(1, train.CargoCapacity)) * 0.35;
            var totalDamage = rawDamage * randomDamageFactor * cargoDamageFactor;
            train.ApplyDamage(totalDamage);
            damageTaken += totalDamage;
            distanceTravelled += segment.DistanceKm;

            var wearIncrease = (0.004 + request.CargoWeight / 20000) * (0.7 + _random.NextDouble() * 0.6);
            segment.Degrade(wearIncrease);

            if (segment.WearLevel >= 0.8)
            {
                events.Add($"Segment '{segment.Name}' is heavily worn and needs maintenance.");
            }

            if (train.CurrentDurability <= 0)
            {
                events.Add("Train is broken and can not continue.");
                break;
            }
        }

        var isCompleted = Math.Abs(distanceTravelled - request.Route.TotalDistanceKm) < 0.001;
        var revenue = isCompleted ? request.ProjectedGrossRevenue : request.ProjectedGrossRevenue * (decimal)(distanceTravelled / request.Route.TotalDistanceKm);

        var missingDurability = train.MaxDurability - train.CurrentDurability;
        var repairCost = (decimal)missingDurability * 3.4m;

        return new TripResult(
            IsCompleted: isCompleted,
            RequiresRepair: train.CurrentDurability < train.MaxDurability * 0.65,
            RequiresRefuel: train.FuelLevel < 25,
            Revenue: decimal.Round(revenue, 2),
            RepairCost: decimal.Round(repairCost, 2),
            FuelCost: decimal.Round(fuelCost, 2),
            DistanceTravelled: distanceTravelled,
            DamageTaken: damageTaken,
            Events: events);
    }
}
