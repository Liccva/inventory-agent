import winreg
import logging
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class WindowsInfo:
    """Класс для хранения информации о Windows"""
    ProductName: Optional[str] = None
    CurrentBuild: Optional[str] = None
    DisplayVersion: Optional[str] = None
    EditionID: Optional[str] = None
    InstallDate: Optional[str] = None
    UBR: Optional[str] = None

    def to_dict(self):
        """Преобразование в словарь для JSON"""
        return {k: v for k, v in asdict(self).items() if v is not None}

    def to_json_compatible(self):
        """Возвращает данные для payload.json"""
        return {
            "os": {
                "ProductName": self.ProductName or "Unknown",
                "CurrentBuild": self.CurrentBuild or "Unknown",
                "DisplayVersion": self.DisplayVersion or "Unknown",
                "EditionID": self.EditionID or "Unknown"
            }
        }


class RegistryReader:
    @staticmethod
    def get_windows_info() -> WindowsInfo:
        """Читает информацию о Windows из реестра"""
        try:
            key_path = r"Software\Microsoft\Windows NT\CurrentVersion"

            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
                product_name = RegistryReader._read_reg_value(key, "ProductName")
                current_build = RegistryReader._read_reg_value(key, "CurrentBuild")
                display_version = RegistryReader._read_reg_value(key, "DisplayVersion")
                edition_id = RegistryReader._read_reg_value(key, "EditionID")
                install_date = RegistryReader._read_reg_value(key, "InstallDate")
                ubr = RegistryReader._read_reg_value(key, "UBR")

                if install_date:
                    try:
                        install_date = datetime.fromtimestamp(int(install_date)).isoformat()
                    except:
                        install_date = str(install_date)

                return WindowsInfo(
                    ProductName=product_name,
                    CurrentBuild=current_build,
                    DisplayVersion=display_version,
                    EditionID=edition_id,
                    InstallDate=install_date,
                    UBR=str(ubr) if ubr is not None else None
                )

        except Exception as e:
            logging.error(f"Ошибка чтения реестра: {e}")
            return WindowsInfo()

    @staticmethod
    def _read_reg_value(key, value_name):
        """Безопасное чтение значения из реестра"""
        try:
            value, _ = winreg.QueryValueEx(key, value_name)
            return value
        except FileNotFoundError:
            return None