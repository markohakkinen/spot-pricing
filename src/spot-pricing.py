import http.client as http_client
import logging
from argparse import ArgumentParser, Namespace
from datetime import datetime, timedelta, timezone
from os import getcwd
from pathlib import Path

from dateutil import relativedelta
from entsoe import DayAheadPrices, DayAheadPricesParser
from excel import ZaptecInvoice
from yaml import safe_load
from zaptec import ChargeHistory, ChargeHistoryParser, UserChargeHistory


class ZaptecSpotPricing:
    """Generate spot pricing invoices"""

    # Fetch more than the selected month to cover timezone differences and long
    # charging sessions.
    EXTEND_FETCH_BY_DAYS = 10

    def __init__(self, args: Namespace) -> None:
        self.args = args

    def create_invoice(self) -> None:
        contract = self._fetch_contract()
        day_ahead_prices = self._fetch_entsoe_data()
        user_charge_histories = self._fetch_zaptec_data()
        results_folder = Path(getcwd()) / "results"
        results_folder.mkdir(parents=True, exist_ok=True)
        ZaptecInvoice().create(
            results_folder / f"invoice-{self.args.year}-{self.args.month}.xlsx",
            self.args.year,
            self.args.month,
            self.args.timezone,
            contract,
            day_ahead_prices,
            user_charge_histories,
        )

    def _fetch_contract(self) -> dict[str, float]:
        path = Path(self.args.contract)
        if not path.exists():
            raise RuntimeError(f"Contract file not found: {self.args.contract}")
        with open(path) as stream:
            content = safe_load(stream)
            return content["contract"]

    def _fetch_entsoe_data(self) -> dict[datetime, float]:
        entsoe_cache_folder = self._get_cache_folder() / "entsoe"
        entsoe_cache_folder.mkdir(parents=True, exist_ok=True)
        entsoe_cache_file = (
            entsoe_cache_folder / f"{self.args.year}-{self.args.month:02}.xml"
        )
        if self.args.ignore_cache or not entsoe_cache_file.exists():
            (start, end) = self._get_fetch_start_end_times()
            data = DayAheadPrices().fetch(start, end)
            with open(entsoe_cache_file, "w", encoding="utf-8") as stream:
                stream.write(data)
        with open(entsoe_cache_file, encoding="utf-8") as stream:
            return DayAheadPricesParser().parse(stream.read())

    def _fetch_zaptec_data(self) -> dict[str, UserChargeHistory]:
        zaptec_cache_folder = self._get_cache_folder() / "zaptec"
        zaptec_cache_folder.mkdir(parents=True, exist_ok=True)
        zaptec_cache_file = (
            zaptec_cache_folder / f"{self.args.year}-{self.args.month:02}.json"
        )
        if self.args.ignore_cache or not zaptec_cache_file.exists():
            (start, end) = self._get_fetch_start_end_times()
            charge_history = ChargeHistory()
            if self.args.zaptec_installation_id:
                installation_id = self.args.zaptec_installation_id
            else:
                available_ids = charge_history.available_installation_ids()
                if len(available_ids) == 0:
                    raise RuntimeError(
                        "No available installations with the given Zaptec credentials!"
                    )
                if len(available_ids) > 1:
                    raise RuntimeError(
                        "Given Zaptec credentials have access to multiple "
                        "installations. Use --zaptec-installation-id argument "
                        "to indicate which one to use!"
                    )
                installation_id = available_ids[0]
            data = ChargeHistory().fetch(installation_id, start, end)
            with open(zaptec_cache_file, "w", encoding="utf-8") as stream:
                stream.write(data)
        with open(zaptec_cache_file, encoding="utf-8") as stream:
            return ChargeHistoryParser().parse(stream.read())

    def _get_cache_folder(self) -> Path:
        return Path(getcwd()) / ".cache"

    def _get_fetch_start_end_times(self) -> tuple[datetime, datetime]:
        start = datetime(
            year=self.args.year,
            month=self.args.month,
            day=1,
            tzinfo=timezone.utc,
        )
        end = start + relativedelta.relativedelta(months=1)
        extend = timedelta(days=self.EXTEND_FETCH_BY_DAYS)
        return (start - extend, end + extend)


def _main() -> None:
    parser = ArgumentParser()
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--month", type=int, required=True)
    parser.add_argument("--contract", default="contract.yaml")
    parser.add_argument("--zaptec-installation-id")
    parser.add_argument("--timezone", default="Europe/Helsinki")
    parser.add_argument("--ignore-cache", action="store_true")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    if args.debug:
        http_client.HTTPConnection.debuglevel = 1
        logging.basicConfig()
        logging.getLogger().setLevel(logging.DEBUG)
        requests_log = logging.getLogger("requests.packages.urllib3")
        requests_log.setLevel(logging.DEBUG)
        requests_log.propagate = True

    ZaptecSpotPricing(args).create_invoice()


if __name__ == "__main__":
    _main()
