import logging
import os

class Logger:
    @staticmethod
    def setup(log_path, level_name='info'):
        """Настройка логирования"""
        os.makedirs(os.path.dirname(log_path), exist_ok=True)

        levels = {
            'debug': logging.DEBUG,
            'info': logging.INFO,
            'warning': logging.WARNING,
            'error': logging.ERROR
        }
        level = levels.get(level_name.lower(), logging.INFO)

        logging.basicConfig(
            level=level,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_path, encoding='utf-8'),
                #logging.StreamHandler()
            ]
        )

        return logging.getLogger(__name__)