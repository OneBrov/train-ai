namespace CoreSim.Simulation;

public sealed class Route
{
    private readonly List<RouteSegment> _segments;

    public Route(string name, IEnumerable<RouteSegment> segments)
    {
        if (string.IsNullOrWhiteSpace(name)) throw new ArgumentException("Route name is required.", nameof(name));

        _segments = [.. segments ?? throw new ArgumentNullException(nameof(segments))];
        if (_segments.Count == 0)
        {
            throw new ArgumentException("Route must contain at least one segment.", nameof(segments));
        }

        Name = name;
    }

    public string Name { get; }
    public IReadOnlyList<RouteSegment> Segments => _segments;

    public double TotalDistanceKm => _segments.Sum(segment => segment.DistanceKm);

    public double AverageWearLevel => _segments.Average(segment => segment.WearLevel);
}
