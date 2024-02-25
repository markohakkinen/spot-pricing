from datetime import datetime
from pathlib import Path

from entsoe import DayAheadPricesParser


def test_parser():
    test_file = Path(__file__).parent / "data" / "entsoe-2023-11.xml"
    with open(test_file) as stream:
        result = DayAheadPricesParser().parse(stream.read())
        assert len(result) == (31 * 24)
        assert result[datetime.fromisoformat("2023-10-31T23:00Z")] == 2.22
        assert result[datetime.fromisoformat("2023-11-01T22:00Z")] == 16.95
        assert result[datetime.fromisoformat("2023-11-17T07:00Z")] == 141.92
        assert result[datetime.fromisoformat("2023-12-01T22:00Z")] == 98.91
