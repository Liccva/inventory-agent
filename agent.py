"""
Windows Inventory Agent
Сбор информации об ОС Windows по команде inventory
"""

import sys
import argparse
import logging
import time
import os
import signal
import threading

from utils.config_reader import ConfigReader
from utils.logger import Logger
from utils.registry_reader import RegistryReader
from core.queue_manager import QueueManager
from core.dispatcher import Dispatcher
from services.inventory_service import InventoryService


class Agent:
    """Класс агента"""

    def __init__(self):
        self.running = True
        self.dispatcher = None
        self.inventory_service = None
        self.queue_manager = None
        self.command_reader_thread = None
        self.result_processor_thread = None
        self.result_processor_running = False

        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

    def signal_handler(self, signum, frame):
        logging.info(f"Получен сигнал {signum}, останавливаем агента...")
        self.running = False

    def run(self, commands_file: str):
        """Основной метод запуска"""

        config_reader = ConfigReader()
        try:
            config = config_reader.read_config()
        except FileNotFoundError as e:
            print(f"Ошибка: {e}")
            sys.exit(1)

        Logger.setup(config['log_path'], config['log_level'])
        logging.info("Агент запущен")
        logging.info(f"Конфиг: уровень={config['log_level']}, "
                     f"лог={config['log_path']}, "
                     f"воркеры={config['inventory_workers']}")

        if not os.path.exists(commands_file):
            logging.error(f"Файл команд не найден: {commands_file}")
            sys.exit(1)

        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.queue_manager = QueueManager(maxsize=100)
        registry_reader = RegistryReader()

        self.inventory_service = InventoryService(
            registry_reader=registry_reader,
            workers_count=config['inventory_workers'],
            script_dir=script_dir
        )

        services = {
            'inventory': self.inventory_service
        }

        self.dispatcher = Dispatcher(self.queue_manager, services)
        self.dispatcher.start()

        self.result_processor_running = True
        self.result_processor_thread = threading.Thread(
            target=self._process_results,
            name="ResultProcessorThread"
        )
        self.result_processor_thread.daemon = False
        self.result_processor_thread.start()

        self.command_reader_thread = threading.Thread(
            target=self._read_and_dispatch_commands,
            args=(commands_file,),
            name="CommandReaderThread"
        )
        self.command_reader_thread.daemon = True
        self.command_reader_thread.start()

        self._wait_for_completion()

        self.result_processor_running = False
        if self.result_processor_thread:
            self.result_processor_thread.join(timeout=5)
            if self.result_processor_thread.is_alive():
                logging.warning("Поток обработки результатов не завершился вовремя")

        self.dispatcher.stop()
        logging.info("Агент завершил работу")

    def _read_and_dispatch_commands(self, file_path: str):
        """Читает команды из файла и добавляет их в очередь"""
        try:
            inventory_count = 0
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if not self.running:
                        break

                    cmd = line.strip()
                    if not cmd:
                        continue

                    if cmd == 'inventory':
                        while self.running:
                            if self.dispatcher.add_task('inventory'):
                                inventory_count += 1
                                logging.info(f"Команда inventory #{inventory_count} добавлена в очередь")
                                break
                            else:
                                logging.warning("Очередь задач переполнена, ожидание 0.5 сек...")
                                time.sleep(0.5)
                    else:
                        logging.debug(f"Команда игнорируется: {cmd}")

                    time.sleep(0.01)

            logging.info(f"Всего команд inventory добавлено в очередь: {inventory_count}")
        except Exception as e:
            logging.error(f"Ошибка чтения файла команд: {e}")
            sys.exit(1)

    def _process_results(self):
        """
        Поток-обработчик результатов
        Забирает результаты из очереди и логирует их, предотвращая переполнение
        """
        while self.result_processor_running or not self.queue_manager.result_queue.empty():
            result = self.queue_manager.get_result()
            if result:
                logging.debug(f"Обработан результат задачи {result.task_id}: статус {result.status.value}")
                self.queue_manager.result_done()
            else:
                time.sleep(0.05)

    def _wait_for_completion(self):
        """
        Ожидание выполнения всех задач и очистки очереди результатов.
        """
        logging.info("Ожидание выполнения всех задач...")

        while self.running:
            stats = self.queue_manager.get_stats()
            service_queue_size = self.inventory_service.get_queue_size()

            if (stats['tasks_added'] > 0 and
                    stats['tasks_added'] == stats['tasks_completed'] + stats['tasks_failed'] and
                    stats['task_queue_size'] == 0 and
                    service_queue_size == 0 and
                    stats['result_queue_size'] == 0):
                logging.info(f"Все задачи выполнены: "
                             f"{stats['tasks_completed']} успешно, "
                             f"{stats['tasks_failed']} с ошибками")
                break

            time.sleep(0.5)


def main():
    parser = argparse.ArgumentParser(description='Windows Inventory Agent')
    parser.add_argument('commands_file', help='Путь к файлу с командами')
    args = parser.parse_args()

    agent = Agent()
    agent.run(args.commands_file)


if __name__ == "__main__":
    main()