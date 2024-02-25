from datetime import datetime
from os import PathLike
from typing import AnyStr

from dateutil import relativedelta
from openpyxl import Workbook
from openpyxl.worksheet.worksheet import Worksheet
from pytz import timezone
from zaptec import UserChargeHistory


class ZaptecInvoice:
    """Create invoice of Zaptec charging based on spot prices"""

    def create(
        self,
        filename: str | PathLike[AnyStr],
        year: int,
        month: int,
        zone: str,
        day_ahead_prices: dict[datetime, float],
        user_charge_histories: dict[str, UserChargeHistory],
    ) -> None:
        (start, end) = self._get_start_end_times(year, month, zone)
        wb = Workbook()
        wb.iso_dates = True
        self._fill_invoising(wb, user_charge_histories)
        self._fill_contract_info(wb)
        self._fill_spot_price(wb, start, end, zone, day_ahead_prices)
        self._fill_charge_histories(wb, start, end, zone, user_charge_histories)
        wb.remove_sheet(wb.get_sheet_by_name("Sheet"))
        wb.save(filename)  # type:ignore

    def _get_start_end_times(
        self, year: int, month: int, zone: str
    ) -> tuple[datetime, datetime]:
        start = datetime(year=year, month=month, day=1)
        end = start + relativedelta.relativedelta(months=1)
        tz = timezone(zone)
        return (tz.localize(start), tz.localize(end))

    def _fill_invoising(
        self, wb: Workbook, user_charge_histories: dict[str, UserChargeHistory]
    ) -> None:
        invoising = wb.create_sheet("Laskutus")
        invoising.column_dimensions["A"].width = 20
        invoising.column_dimensions["B"].width = 20
        invoising.column_dimensions["C"].width = 16
        invoising.column_dimensions["D"].width = 16
        invoising.column_dimensions["E"].width = 16
        invoising.column_dimensions["F"].width = 20
        invoising.column_dimensions["G"].width = 20
        invoising.column_dimensions["H"].width = 20
        invoising.column_dimensions["I"].width = 20
        invoising.append(
            [
                "Tili",
                "Käyttäjä",
                "Kulutus kWh",
                "Hinta € ALV 24%",
                "Hinta € ALV 0%",
                "Hinta c/kWh ALV 24%",
                "Hinta c/kWh ALV 0%",
                "Spot hinta c/kWh ALV 24%",
                "Spot hinta c/kWh ALV 0%",
            ]
        )
        last_row = 0
        for i, (user, charge_history) in enumerate(user_charge_histories.items()):
            invoising.append(
                [
                    user,
                    charge_history.full_name,
                    f"=SUM('{user}'!B:B)",
                    f"=SUM('{user}'!F:F)",
                    f"=D{i+2}/1.24",
                    f"=D{i+2}/C{i+2}*100",
                    f"=E{i+2}/C{i+2}*100",
                    f"=F{i+2}-'Sähkösopimus'!B5",
                    f"=G{i+2}-'Sähkösopimus'!B5/1.24",
                ]
            )
            last_row = i
        invoising.append(
            [
                "Yhteensä",
                "",
                f"=SUM(C2:C{last_row+2})",
                f"=SUM(D2:D{last_row+2})",
                f"=SUM(E2:E{last_row+2})",
                f"=D{last_row+3}/C{last_row+3}*100",
                f"=E{last_row+3}/C{last_row+3}*100",
                f"=F{last_row+3}-'Sähkösopimus'!B5",
                f"=G{last_row+3}-'Sähkösopimus'!B5/1.24",
            ]
        )
        for i in range(2, last_row + 4):
            invoising[f"D{i}"].number_format = "0.00"
            invoising[f"E{i}"].number_format = "0.00"
            invoising[f"F{i}"].number_format = "0.00"
            invoising[f"G{i}"].number_format = "0.00"
            invoising[f"H{i}"].number_format = "0.00"
            invoising[f"I{i}"].number_format = "0.00"

    def _fill_contract_info(self, wb: Workbook) -> None:
        contract_info: Worksheet = wb.create_sheet("Sähkösopimus")
        contract_info.column_dimensions["A"].width = 20
        contract_info.column_dimensions["B"].width = 20
        contract_info.append(["", "c/kWh ALV 24%"])
        contract_info.append(["Sähkönsiirto", 3.09])
        contract_info.append(["Vero", 2.79372])
        contract_info.append(["Välityspalkkio", 0.496])
        contract_info.append(["Kiinteä tuntihinta", "=SUM(B2:B4)"])

    def _fill_charge_histories(
        self,
        wb: Workbook,
        start: datetime,
        end: datetime,
        zone: str,
        user_charge_histories: dict[str, UserChargeHistory],
    ) -> None:
        for user, charge_history in user_charge_histories.items():
            user_consumption_sheet: Worksheet = wb.create_sheet(user)
            self._fill_user_consumption_sheet(
                user_consumption_sheet, start, end, zone, charge_history
            )

    def _fill_user_consumption_sheet(
        self,
        user_consumption_sheet: Worksheet,
        start: datetime,
        end: datetime,
        zone: str,
        charge_history: UserChargeHistory,
    ) -> None:
        user_consumption_sheet.column_dimensions["A"].width = 20
        user_consumption_sheet.column_dimensions["B"].width = 20
        user_consumption_sheet.column_dimensions["C"].width = 20
        user_consumption_sheet.column_dimensions["D"].width = 20
        user_consumption_sheet.column_dimensions["E"].width = 20
        user_consumption_sheet.column_dimensions["F"].width = 20
        user_consumption_sheet.append(
            [
                "Aika (UTC)",
                "Kulutus kWh",
                "Spot hinta c/kWh ALV 24%",
                "Spot hinta € ALV 24%",
                "Kiinteä hinta € ALV 24%",
                "Hinta € ALV 24%",
            ]
        )
        sorted_consumption = dict(sorted(charge_history.consumption.items()))
        row = 2
        for key, value in sorted_consumption.items():
            if (key >= start) and (key < end):
                time = key.astimezone(timezone(zone)).replace(tzinfo=None)
                user_consumption_sheet.append(
                    [
                        time,
                        value,
                        f"=VLOOKUP(A{row},'Spot-hinta'!A:D,4,TRUE)",
                        f"=B{row}*C{row}/100",
                        f"='Sähkösopimus'!$B$5*B{row}/100",
                        f"=D{row}+E{row}",
                    ]
                )
                row += 1

    def _fill_spot_price(
        self,
        wb: Workbook,
        start: datetime,
        end: datetime,
        zone: str,
        day_ahead_prices: dict[datetime, float],
    ) -> None:
        spot_price_sheet: Worksheet = wb.create_sheet("Spot-hinta")
        spot_price_sheet.column_dimensions["A"].width = 20
        spot_price_sheet.column_dimensions["B"].width = 16
        spot_price_sheet.column_dimensions["C"].width = 16
        spot_price_sheet.column_dimensions["D"].width = 16
        spot_price_sheet.append(
            [f"Aika ({zone})", "€/MWh (ALV 0%)", "c/kWh (ALV 0%)", "c/kWh (ALV 24%)"]
        )
        row = 2
        for key, value in day_ahead_prices.items():
            if (key >= start) and (key < end):
                time = key.astimezone(timezone(zone)).replace(tzinfo=None)
                spot_price_sheet.append(
                    [time, value, f"=B{row}/1000*100", f"=C{row}*1.24"]
                )
                row += 1
