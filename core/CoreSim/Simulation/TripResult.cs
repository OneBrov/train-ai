namespace CoreSim.Simulation;

public sealed record TripResult(
    bool IsCompleted,
    bool RequiresRepair,
    bool RequiresRefuel,
    decimal Revenue,
    decimal RepairCost,
    decimal FuelCost,
    double DistanceTravelled,
    double DamageTaken,
    IReadOnlyList<string> Events)
{
    public decimal NetProfit => Revenue - RepairCost - FuelCost;
}
