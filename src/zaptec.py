from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from json import dumps, loads
from os import getenv
from typing import Any, cast

from requests import Session, post


class ChargeHistory:
    """Fetch charge history from Zaptec

    API documented at https://api.zaptec.com/help/index.html
    """

    def __init__(self) -> None:
        self.user_name = getenv("ZAPTEC_USERNAME")
        self.password = getenv("ZAPTEC_PASSWORD")
        self.api_key = getenv("ZAPTEC_APIKEY")
        if not ((self.user_name and self.password) or self.api_key):
            raise RuntimeError(
                "Missing Zaptec username and password or API key! "
                "Set either environment variables ZAPTEC_USERNAME and ZAPTEC_PASSWORD "
                "or ZAPTEC_APIKEY."
            )

    def fetch(self, installation_id: str, start: datetime, end: datetime) -> str:
        with self._create_session() as session:
            first_page = self._fetch_page(session, 0, installation_id, start, end)
            data = first_page["Data"]
            pages = first_page["Pages"]
            for page in range(1, pages):
                current_page = self._fetch_page(
                    session, page, installation_id, start, end
                )
                data.extend(current_page["Data"])
            return dumps({"Data": data}, ensure_ascii=False)

    def available_installation_ids(self) -> list[str]:
        with self._create_session() as session:
            installations_json = self._fetch_installations(session)
            data = installations_json["Data"]
            return [item["Id"] for item in data]

    def _fetch_page(
        self,
        session: Session,
        page: int,
        installation_id: str,
        start: datetime,
        end: datetime,
    ) -> Any:  # noqa: ANN401
        params = {
            "InstallationId": installation_id,
            "From": start.isoformat(),
            "To": end.isoformat(),
            "DetailLevel": "1",
            "PageSize": "10",
            "PageIndex": str(page),
        }
        headers = {"Accept": "text/plain"}
        r = session.get(
            "https://api.zaptec.com/api/chargehistory",
            params=params,
            headers=headers,
        )
        r.raise_for_status()
        return r.json()

    def _fetch_installations(self, session: Session) -> Any:  # noqa: ANN401
        params = {"ReturnIdNameOnly": True}
        headers = {"Accept": "text/plain"}
        r = session.get(
            "https://api.zaptec.com/api/installation", params=params, headers=headers
        )
        r.raise_for_status()
        return r.json()

    def _get_token(self) -> str:
        token_response = post(
            "https://api.zaptec.com/oauth/token",
            data={
                "grant_type": "password",
                "username": self.user_name,
                "password": self.password,
            },
            headers={
                "content-type": "application/x-www-form-urlencoded",
            },
            allow_redirects=False,
        )
        token_response.raise_for_status()
        return token_response.json()["access_token"]

    def _create_session(self) -> Session:
        session = Session()
        if self.api_key:
            session.headers.update({"X-Api-Key": self.api_key})
        else:
            token = self._get_token()
            session.headers.update({"Authorization": f"Bearer {token}"})
        return session


def time_floor(time: datetime, floor_to_seconds: int = 15 * 60) -> datetime:
    seconds = (time.replace(tzinfo=None) - datetime.min).seconds
    rounding = seconds // floor_to_seconds * floor_to_seconds
    return time + timedelta(seconds=rounding - seconds, microseconds=-time.microsecond)


def fallback_utc(time: datetime) -> datetime:
    if time.tzinfo is not None:
        return time
    return datetime(
        time.year,
        time.month,
        time.day,
        time.hour,
        time.minute,
        time.second,
        time.microsecond,
        timezone.utc,
    )


@dataclass
class UserChargeHistory:
    user_name: str
    full_name: str
    consumption: dict[datetime, float]


class ChargeHistoryParser:
    """Parse document received from Zaptec

    Retrieve charge history for all users found from the document.
    """

    def parse(self, data: str) -> dict[str, UserChargeHistory]:
        result = {}
        parsed = loads(data)
        data_item = parsed["Data"]
        for item in data_item:
            id = item["Id"] if "Id" in item else "<unknown-id>"
            if "UserUserName" not in item:
                if float(item["Energy"]) > 0:
                    raise RuntimeError(
                        f"Found charging session {id} without user identification!"
                    )
                continue
            try:
                user_name = item["UserUserName"]  # type:ignore
                history = result.get(  # type:ignore
                    user_name,
                    UserChargeHistory(user_name, item["UserFullName"], {}),  # type:ignore
                )
                session_energy = float(item["Energy"])  # type:ignore
                if "EnergyDetails" in item:
                    energy_details = item["EnergyDetails"]  # type:ignore
                    self._update_history_with_energy_details(
                        cast(UserChargeHistory, history),
                        energy_details,
                        session_energy,
                    )
                else:
                    print(
                        f"WARNING: EnergyDetails not found for {id}. "
                        "Zaptec has not recorded details, using fallback."
                    )
                    self._update_history_with_session_energy(
                        cast(UserChargeHistory, history),
                        session_energy,
                        fallback_utc(datetime.fromisoformat(item["StartDateTime"])),
                        fallback_utc(datetime.fromisoformat(item["EndDateTime"])),
                    )
                result[user_name] = history  # type:ignore
            except KeyError as ex:
                raise Exception(f"Error with id {id}") from ex
        return dict(sorted(result.items()))  # type:ignore

    def _update_history_with_energy_details(
        self,
        history: UserChargeHistory,
        energy_details: Any,  # noqa: ANN401
        session_energy: float,
    ) -> None:
        detail_energy_total = 0.0
        for i, energy_detail in enumerate(energy_details):
            timestamp = datetime.fromisoformat(energy_detail["Timestamp"])  # type:ignore
            energy = float(energy_detail["Energy"])  # type:ignore
            if energy > 0:
                consumption_start = (
                    time_floor(timestamp)
                    if i == len(energy_details) - 1
                    else time_floor(timestamp) - timedelta(minutes=15)
                )
                if consumption_start in history.consumption:  # type:ignore
                    raise RuntimeError
                history.consumption[consumption_start] = energy  # type:ignore
                detail_energy_total += energy
        assert abs(session_energy - detail_energy_total) < 0.0001

    def _update_history_with_session_energy(
        self,
        history: UserChargeHistory,
        session_energy: float,
        start_time: datetime,
        end_time: datetime,
    ) -> None:
        detail_energy_total = 0.0
        charge_duration = end_time - start_time
        time = time_floor(start_time)
        while time < end_time:
            duration = self._duration(time, start_time, end_time)
            ratio = duration / charge_duration
            energy = ratio * session_energy
            history.consumption[time] = energy
            time += timedelta(minutes=15)
            detail_energy_total += energy
        assert abs(session_energy - detail_energy_total) < 0.0001

    @staticmethod
    def _duration(
        time: datetime, start_time: datetime, end_time: datetime
    ) -> timedelta:
        start = time if time > start_time else start_time
        end = (
            time + timedelta(minutes=15)
            if time + timedelta(minutes=15) < end_time
            else end_time
        )
        return end - start
