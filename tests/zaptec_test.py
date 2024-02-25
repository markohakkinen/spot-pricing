from datetime import datetime, timezone
from pathlib import Path

from zaptec import ChargeHistoryParser, time_floor


def test_parser():
    test_file = Path(__file__).parent / "data" / "zaptec-2023-11.json"
    with open(test_file) as stream:
        result = ChargeHistoryParser().parse(stream.read())
        assert len(result) == 1
        history = result["matti.meikalainen@example.com"]
        consumption = history.consumption
        assert len(history.consumption) == 142 - 20
        assert (
            consumption[datetime.fromisoformat("2023-12-09T13:00Z")]
            == 0.2990000000000066
        )
        assert (
            consumption[datetime.fromisoformat("2023-12-07T22:45Z")]
            == 2.8170000000000073
        )
        assert (
            consumption[datetime.fromisoformat("2023-12-05T03:45Z")]
            == 0.9230000000000018
        )


def test_time_floor():
    floored1 = time_floor(datetime.fromisoformat("2023-12-01T20:29:59.999Z"))
    floored2 = time_floor(
        datetime(2023, 12, 10, 9, 31, 22, 473000, tzinfo=timezone.utc)
    )
    assert floored1 == datetime.fromisoformat("2023-12-01T20:15Z")
    assert floored2 == datetime.fromisoformat("2023-12-10T09:30Z")
