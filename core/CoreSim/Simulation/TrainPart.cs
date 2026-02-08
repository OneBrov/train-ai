namespace CoreSim.Simulation;

public sealed record TrainPart(
    string Name,
    TrainPartType PartType,
    double DurabilityBoost,
    double SpeedMultiplier,
    double CargoCapacityBoost,
    double FuelEfficiencyMultiplier,
    decimal Cost)
{
    public static TrainPart ReinforcedWheels => new(
        "Reinforced Wheels",
        TrainPartType.Wagon,
        DurabilityBoost: 12,
        SpeedMultiplier: 1.0,
        CargoCapacityBoost: 0,
        FuelEfficiencyMultiplier: 1.0,
        Cost: 1100);

    public static TrainPart TurboEngine => new(
        "Turbo Engine",
        TrainPartType.Engine,
        DurabilityBoost: 0,
        SpeedMultiplier: 1.18,
        CargoCapacityBoost: 0,
        FuelEfficiencyMultiplier: 0.91,
        Cost: 2000);

    public static TrainPart CargoPods => new(
        "Cargo Pods",
        TrainPartType.Cargo,
        DurabilityBoost: 0,
        SpeedMultiplier: 0.96,
        CargoCapacityBoost: 20,
        FuelEfficiencyMultiplier: 0.97,
        Cost: 900);
}
