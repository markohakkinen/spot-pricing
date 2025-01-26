import smtplib
from datetime import datetime
from email.headerregistry import Address
from email.message import EmailMessage
from mimetypes import guess_type
from os import getenv
from pathlib import Path
from ssl import create_default_context
from subprocess import run
from typing import Any

from dateutil import relativedelta
from yaml import safe_load


class EmailGenerator:
    def __init__(self, config_file: Path) -> None:
        self._config = self._read_config(config_file)

    def generate_message(
        self, year: int, month: int, attachment_filename: Path
    ) -> EmailMessage:
        message = EmailMessage()
        message["Subject"] = self._config["subject"].format(year=year, month=month)
        message["From"] = Address(
            display_name=self._config["from"]["display_name"],
            addr_spec=self._config["from"]["address"],
        )
        message["To"] = self._get_addresses("to")
        message["Cc"] = self._get_addresses("cc")
        message["Bcc"] = self._get_addresses("bcc")
        message.set_content(self._config["message"].format(year=year, month=month))
        self._add_attachement(message, attachment_filename)
        return message

    def _get_addresses(self, config_key: str) -> list[Address]:
        if config_key not in self._config or not self._config[config_key]:
            return []
        return [
            Address(display_name=to["display_name"], addr_spec=to["address"])
            for to in self._config[config_key]
        ]

    @staticmethod
    def _read_config(config_file: Path) -> dict[str, Any]:
        if not config_file.exists():
            raise RuntimeError(f"Email config file not found: {config_file}")
        with open(config_file) as stream:
            return safe_load(stream)["email"]

    @staticmethod
    def _add_attachement(message: EmailMessage, filename: Path) -> None:
        ctype, encoding = guess_type(filename)
        if ctype is None or encoding is not None:
            ctype = "application/octet-stream"
        maintype, subtype = ctype.split("/", 1)
        with open(filename, "rb") as stream:
            message.add_attachment(
                stream.read(),
                maintype=maintype,
                subtype=subtype,
                filename=filename.name,
            )


class MailSender:
    def __init__(self, config_file: Path) -> None:
        self._config = self._read_config(config_file)
        password = getenv(self._config["password_env_variable"])
        if password is None:
            raise RuntimeError(
                f"Environment variable {self._config['password_env_variable']} not set!"
            )
        self._password = password

    def send(self, message: EmailMessage) -> None:
        context = create_default_context()
        server = smtplib.SMTP(host=self._config["host"], port=self._config["port"])
        try:
            response = server.starttls(context=context)
            if response[0] != 220:
                raise Exception("Connection not secure!")
            server.login(user=self._config["user"], password=self._password)
            print("Message\n\n")
            print(message)
            print("\nSending...\n")
            server.send_message(message)
        finally:
            server.quit()

    @staticmethod
    def _read_config(config_file: Path) -> dict[str, Any]:
        if not config_file.exists():
            raise RuntimeError(f"Email config file not found: {config_file}")
        with open(config_file) as stream:
            return safe_load(stream)["smtp_starttls"]


def generate_invoice(year: int, month: int) -> Path:
    path = Path(f"results/invoice-{year}-{month}.xlsx")
    if path.exists():
        path.unlink()
    run(
        [
            "python",
            "spot-pricing.py",
            "--year",
            str(year),
            "--month",
            str(month),
            "--ignore-cache",
        ]
    )
    if not path.exists():
        raise RuntimeError("Invoice generation failed!")
    return path


if __name__ == "__main__":
    email_config_file = Path("email_config.yaml")
    last_month = datetime.now() - relativedelta.relativedelta(months=1)
    invoice_filename = generate_invoice(last_month.year, last_month.month)
    message = EmailGenerator(email_config_file).generate_message(
        last_month.year, last_month.month, invoice_filename
    )
    MailSender(email_config_file).send(message)
