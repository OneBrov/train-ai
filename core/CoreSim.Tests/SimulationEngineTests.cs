using CoreSim.Simulation;

namespace CoreSim.Tests;

public class SimulationEngineTests
{
    [Test]
    public void ExecuteTrip_DegradesRouteAndDamagesTrain()
    {
        var random = new SequenceRandom(0.2, 0.8, 0.4, 0.9);
        var engine = new SimulationEngine(random);
        var route = new Route("Steppe", [
            new RouteSegment("Old Bridge", 120, 0.7),
            new RouteSegment("Desert Line", 80, 0.5)
        ]);
        var train = new Train("Nomad", baseSpeed: 90, maxDurability: 100, baseCargoCapacity: 60, baseFuelPerKilometer: 0.18);
        train.AddPart(TrainPart.ReinforcedWheels);

        var result = engine.ExecuteTrip(train, new TripRequest(route, CargoWeight: 40, CargoRatePerKm: 22));

        Assert.That(result.DistanceTravelled, Is.EqualTo(200).Within(0.001));
        Assert.That(result.IsCompleted, Is.True);
        Assert.That(route.AverageWearLevel, Is.GreaterThan(0));
        Assert.That(train.CurrentDurability, Is.LessThan(train.MaxDurability));
        Assert.That(result.DamageTaken, Is.GreaterThan(0));
        Assert.That(result.Revenue, Is.EqualTo(4400m));
    }

    [Test]
    public void ExecuteTrip_ReturnsFailedResult_WhenCargoExceedsCapacity()
    {
        var engine = new SimulationEngine(new SequenceRandom(0.5));
        var route = new Route("Any", [new RouteSegment("Any", 10, 0.3)]);
        var train = new Train("Scout", baseSpeed: 80, maxDurability: 100, baseCargoCapacity: 20, baseFuelPerKilometer: 0.2);

        var result = engine.ExecuteTrip(train, new TripRequest(route, CargoWeight: 25, CargoRatePerKm: 10));

        Assert.That(result.IsCompleted, Is.False);
        Assert.That(result.DistanceTravelled, Is.Zero);
        Assert.That(result.Events, Has.Count.EqualTo(1));
        Assert.That(result.Events[0], Does.Contain("above train capacity"));
    }

    [Test]
    public void TrainCustomization_ChangesPerformance()
    {
        var train = new Train("Builder", baseSpeed: 100, maxDurability: 120, baseCargoCapacity: 50, baseFuelPerKilometer: 0.2);

        train.AddPart(TrainPart.TurboEngine);
        train.AddPart(TrainPart.CargoPods);

        Assert.That(train.EffectiveSpeed, Is.EqualTo(113.28).Within(0.01));
        Assert.That(train.CargoCapacity, Is.EqualTo(70).Within(0.001));
        Assert.That(train.EffectiveFuelPerKilometer, Is.EqualTo(0.17654).Within(0.0001));
    }

    [Test]
    public void ExecuteTrip_StopsWhenFuelIsNotEnough()
    {
        var random = new SequenceRandom(0.2, 0.2, 0.2, 0.2);
        var engine = new SimulationEngine(random);
        var route = new Route("Long haul", [
            new RouteSegment("A", 200, 0.4),
            new RouteSegment("B", 200, 0.4),
            new RouteSegment("C", 200, 0.4)
        ]);

        var train = new Train("Light", baseSpeed: 90, maxDurability: 90, baseCargoCapacity: 100, baseFuelPerKilometer: 0.25);

        var result = engine.ExecuteTrip(train, new TripRequest(route, CargoWeight: 50, CargoRatePerKm: 15));

        Assert.That(result.IsCompleted, Is.False);
        Assert.That(result.Events.Any(e => e.Contains("Out of fuel")), Is.True);
        Assert.That(result.DistanceTravelled, Is.LessThan(route.TotalDistanceKm));
    }

    private sealed class SequenceRandom : IRandom
    {
        private readonly Queue<double> _values;

        public SequenceRandom(params double[] values)
        {
            _values = new Queue<double>(values);
        }

        public double NextDouble()
        {
            if (_values.Count == 0)
            {
                return 0.5;
            }

            return _values.Dequeue();
        }
    }
}
