"""
Сервис диспетчеризации
Его функции включают:
- Управление очередью: обработка входящих задач
- Валидация: проверка легитимности команды - сопоставление команды с разрешенным списком действий
- Диспетчеризация: в зависимости от содержания входящей команды передавать выполнение задачи конкретному
  сервису, перекладывая её в соответствующую очередь
"""

import logging
import time
from threading import Thread
from typing import Dict, Any
from core.queue_manager import QueueManager, Task, Result


class Dispatcher:
    """
    Диспетчер задач - управляет очередью и распределяет задачи по сервисам
    """

    def __init__(self, queue_manager: QueueManager, services: Dict[str, Any]):
        self.queue_manager = queue_manager
        self.services = services
        self.running = False
        self.thread = None

        self.allowed_commands = list(services.keys())

        self.tasks_dispatched = 0
        self.tasks_rejected = 0

        for service in services.values():
            if hasattr(service, 'start'):
                service.start()

            if hasattr(service, 'set_result_callback'):
                service.set_result_callback(self._on_service_result)

        logging.info(f"Диспетчер инициализирован. Команды: {self.allowed_commands}")

    def _on_service_result(self, result: Result):
        """
        Callback для получения результатов от сервисов
        """
        self.queue_manager.add_result(result)
        logging.debug(f"Получен результат от сервиса для задачи {result.task_id}")

    def start(self):
        """Запуск диспетчера"""
        if self.running:
            return

        self.running = True
        self.thread = Thread(target=self._dispatch_loop, name="DispatcherThread")
        self.thread.daemon = True
        self.thread.start()
        logging.info("Диспетчер запущен")

    def stop(self):
        """Остановка диспетчера"""
        self.running = False

        for service in self.services.values():
            if hasattr(service, 'stop'):
                service.stop()

        logging.info("Диспетчер остановлен")

    def _dispatch_loop(self):
        """
        Основной цикл диспетчеризации
        """
        logging.info("Цикл диспетчеризации запущен")

        while self.running:
            try:
                task = self.queue_manager.get_task()

                if task:
                    if self._validate_task(task):
                        self._dispatch_to_service(task)
                    else:
                        self.tasks_rejected += 1
                        result = Result.failure(task, f"Команда '{task.command}' не разрешена")
                        self.queue_manager.add_result(result)
                        self.queue_manager.task_done()
                else:
                    time.sleep(0.05)

            except Exception as e:
                logging.error(f"Ошибка в цикле диспетчеризации: {e}")
                time.sleep(1)

        logging.info(f"Цикл диспетчеризации завершен. "
                    f"Отправлено: {self.tasks_dispatched}, отклонено: {self.tasks_rejected}")

    def _validate_task(self, task: Task) -> bool:
        """Валидация команды"""
        if task.command not in self.allowed_commands:
            logging.warning(f"Команда '{task.command}' не разрешена")
            return False

        logging.debug(f"Задача {task.task_id} прошла валидацию")
        return True

    def _dispatch_to_service(self, task: Task):
        """
        Диспетчеризация задачи сервису
        """
        service = self.services.get(task.command)

        if not service:
            logging.error(f"Сервис для команды '{task.command}' не найден")
            self.tasks_rejected += 1
            result = Result.failure(task, f"Сервис не найден")
            self.queue_manager.add_result(result)
            self.queue_manager.task_done()
            return

        try:
            if service.add_task(task):
                self.tasks_dispatched += 1
                logging.info(f"Задача {task.task_id} передана сервису {task.command} "
                            f"(очередь сервиса: {service.get_queue_size()})")
            else:
                self.tasks_rejected += 1
                logging.error(f"Сервис {task.command} не принял задачу {task.task_id} (очередь переполнена)")
                result = Result.failure(task, "Очередь сервиса переполнена")
                self.queue_manager.add_result(result)
                self.queue_manager.task_done()

        except Exception as e:
            self.tasks_rejected += 1
            logging.error(f"Ошибка при передаче задачи {task.task_id}: {e}")
            result = Result.failure(task, str(e))
            self.queue_manager.add_result(result)
            self.queue_manager.task_done()

    def add_task(self, command: str, data: Any = None) -> bool:
        """
        Публичный метод для добавления задач в очередь
        """
        task = Task.create(command, data)
        return self.queue_manager.add_task(task)