from datetime import datetime, timedelta, timezone

from solar_store.repository import compute_inverter_energy_delta


def test_uses_last_value_before_start_for_period_delta():
    samples = [
        (datetime(2024, 1, 1, 8, 0, tzinfo=timezone.utc), 100.0),
        (datetime(2024, 1, 3, 8, 0, tzinfo=timezone.utc), 180.0),
        (datetime(2024, 1, 5, 8, 0, tzinfo=timezone.utc), 260.0),
    ]

    start = datetime(2024, 1, 4, 0, 0, tzinfo=timezone.utc)
    end = datetime(2024, 1, 6, 0, 0, tzinfo=timezone.utc)

    assert compute_inverter_energy_delta(samples, start, end) == 80.0


def test_uses_first_available_sample_when_range_starts_after_history():
    samples = [
        (datetime(2024, 1, 10, 8, 0, tzinfo=timezone.utc), 50.0),
        (datetime(2024, 1, 12, 8, 0, tzinfo=timezone.utc), 90.0),
    ]

    start = datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc)
    end = datetime(2024, 1, 13, 0, 0, tzinfo=timezone.utc)

    assert compute_inverter_energy_delta(samples, start, end) == 40.0


def test_ignores_lifetime_counter_resets_inside_period():
    samples = [
        (datetime(2024, 1, 1, 8, 0, tzinfo=timezone.utc), 100.0),
        (datetime(2024, 1, 3, 8, 0, tzinfo=timezone.utc), 180.0),
        (datetime(2024, 1, 5, 8, 0, tzinfo=timezone.utc), 2.0),
        (datetime(2024, 1, 6, 8, 0, tzinfo=timezone.utc), 42.0),
    ]

    start = datetime(2024, 1, 2, 0, 0, tzinfo=timezone.utc)
    end = datetime(2024, 1, 7, 0, 0, tzinfo=timezone.utc)

    assert compute_inverter_energy_delta(samples, start, end) == 120.0
