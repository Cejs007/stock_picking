def calculate_composite(
    results: dict[str, tuple[float | None, list[str]]],
    weights: dict[str, float],
) -> tuple[float | None, list[str], list[str]]:
    all_warnings: list[str] = []
    for _, w in results.values():
        all_warnings.extend(w)

    active = {
        name: (value, weights.get(name, 0.0))
        for name, (value, _) in results.items()
        if value is not None and weights.get(name, 0.0) > 0
    }

    if not active:
        return None, [], all_warnings

    total_weight = sum(w for _, w in active.values())
    fair_value = sum(v * w / total_weight for v, w in active.values())
    return fair_value, list(active.keys()), all_warnings
