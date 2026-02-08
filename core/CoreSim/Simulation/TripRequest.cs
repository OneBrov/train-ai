namespace CoreSim.Simulation;

public sealed record TripRequest(Route Route, double CargoWeight, decimal CargoRatePerKm)
{
    public decimal ProjectedGrossRevenue => (decimal)Route.TotalDistanceKm * CargoRatePerKm;
}
