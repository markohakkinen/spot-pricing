import re
from datetime import datetime, timedelta
from os import getenv
from xml.etree import ElementTree

from requests import get


class DayAheadPrices:
    """Fetch day ahead prices from ENTSO-E service

    RESTful API documentation at
    https://transparency.entsoe.eu/content/static_content/Static%20content/web%20api/Guide.html
    """

    def __init__(self) -> None:
        self.api_token = getenv("ENTSOE_API_TOKEN")
        if not self.api_token:
            raise RuntimeError(
                "Missing ENTSO-E API token! "
                "Set environment variable ENTSOE_API_TOKEN."
            )

    def fetch(self, start: datetime, end: datetime) -> str:
        time_start = start.strftime("%Y-%m-%dT%H:%MZ")
        time_end = end.strftime("%Y-%m-%dT%H:%MZ")
        time_interval = f"{time_start}/{time_end}"
        r = get(
            "https://web-api.tp.entsoe.eu/api",
            params={
                "securityToken": self.api_token,
                "documentType": "A44",
                "TimeInterval": time_interval,
                "in_domain": "10YFI-1--------U",
                "out_domain": "10YFI-1--------U",
            },
        )
        r.raise_for_status()
        return r.text


class DayAheadPricesParser:
    """Parse document received from ENTSO-E

    Retrieve hourly pricing information.
    """

    def parse(self, data: str) -> dict[datetime, float]:
        result = {}
        root = ElementTree.fromstring(data)
        ns = {"doc": re.match(r"\{(.*)\}", root.tag).group(1)}  # type: ignore
        for time_series in root.findall(".//doc:TimeSeries", ns):
            time_interval = time_series.find(".//doc:timeInterval", ns)
            start = time_interval.find("doc:start", ns)  # type: ignore
            start_time = datetime.fromisoformat(start.text)  # type: ignore
            resolution = time_series.find(".//doc:resolution", ns)
            resolution_minutes = int(re.match(r"PT(\d*)M", resolution.text).group(1))  # type: ignore
            for point in time_series.findall(".//doc:Point", ns):
                position = int(point.find("doc:position", ns).text)  # type: ignore
                price = float(point.find("doc:price.amount", ns).text)  # type: ignore
                delta = timedelta(minutes=resolution_minutes * (position - 1))
                time = start_time + delta
                result[time] = price
        return dict(sorted(result.items()))  # type: ignore
