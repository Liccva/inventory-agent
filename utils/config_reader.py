import configparser
import os
import sys


class ConfigReader:
    def __init__(self):
        self.executable_dir = self._get_executable_dir()
        self.config_path = os.path.join(self.executable_dir, 'config.ini')

    def _get_executable_dir(self):
        """Возвращает директорию исполняемого файла (agent.py)"""
        if getattr(sys, 'frozen', False):
            return os.path.dirname(sys.executable)

        main_script = sys.argv[0]
        if os.path.isabs(main_script):
            return os.path.dirname(main_script)
        else:
            return os.path.dirname(os.path.abspath(main_script))

    def read_config(self):
        """Читает конфигурационный файл"""
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Конфиг не найден: {self.config_path}")

        config = configparser.ConfigParser()
        config.read(self.config_path, encoding='utf-8')

        log_path_config = config['logging'].get('log_path', '.').replace('.\\', '').replace('./', '')

        return {
            'log_level': config['logging'].get('level', 'info'),
            'log_path': os.path.join(self.executable_dir, log_path_config, 'log.txt'),
            'inventory_workers': int(config['workers'].get('InventoryWorkers', 1))
        }