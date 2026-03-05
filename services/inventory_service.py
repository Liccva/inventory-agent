"""
Сервис инвентаризации
Сервис, отвечающий за сбор данных о системе. При получении задачи «inventory» он
инициирует сбор информации о версии ОС Windows и записывает результат в файл
"""

import logging
import json
import os
import time
import threading
from threading import Thread, Lock
from typing import List, Optional
from queue import Queue, Empty

from core.queue_manager import Task, Result


class InventoryWorker(Thread):
    """
    Отдельный воркер для выполнения задач инвентаризации
    Запускается в своем потоке и обрабатывает поступающие задачи
    """

    def __init__(self, worker_id: int, registry_reader, script_dir: str,
                 task_queue: Queue, result_callback, file_lock: Lock):
        """
        Args:
            worker_id: ID воркера
            registry_reader: Читатель реестра
            script_dir: Директория скрипта
            task_queue: Очередь задач для этого воркера
            result_callback: Функция для отправки результата
            file_lock: Общий Lock для синхронизации записи в файл
        """
        super().__init__(name=f"InventoryWorker-{worker_id}")
        self.worker_id = worker_id
        self.registry_reader = registry_reader
        self.script_dir = script_dir
        self.task_queue = task_queue
        self.result_callback = result_callback
        self.file_lock = file_lock  # используем общий Lock, переданный из сервиса
        self.running = True
        self.daemon = True
        self.tasks_processed = 0
        self.active_task = None

        logging.info(f"Воркер {worker_id} создан и готов к работе")

    def run(self):
        """Основной цикл воркера"""
        logging.info(f"Воркер {self.worker_id} запущен и ожидает задачи")

        while self.running:
            try:

                try:
                    task = self.task_queue.get(timeout=0.5)
                    self.active_task = task
                except Empty:
                    continue

                logging.info(f"Воркер {self.worker_id} начал обработку задачи {task.task_id}")

                start_time = time.time()
                result = self._process_task(task)
                processing_time = time.time() - start_time

                self.tasks_processed += 1
                logging.info(f"Воркер {self.worker_id} завершил задачу {task.task_id} за {processing_time:.5f} сек (всего обработано: {self.tasks_processed})")

                if self.result_callback:
                    self.result_callback(result)

                self.task_queue.task_done()
                self.active_task = None

            except Exception as e:
                logging.error(f"Воркер {self.worker_id}: ошибка {e}")
                time.sleep(0.1)

        logging.info(f"Воркер {self.worker_id} остановлен (обработано задач: {self.tasks_processed})")

    def _process_task(self, task: Task) -> Result:
        """Обработка задачи"""
        try:

            windows_info = self.registry_reader.get_windows_info()

            self._save_to_file(windows_info)

            result = Result.success(task, windows_info.to_json_compatible())

            logging.debug(f"Воркер {self.worker_id} успешно выполнил задачу {task.task_id}")
            logging.debug(f"OS Info: {windows_info.ProductName}")

            return result

        except Exception as e:
            logging.error(f"Воркер {self.worker_id} ошибка при выполнении задачи {task.task_id}: {e}")
            return Result.failure(task, str(e))

    def _save_to_file(self, windows_info):
        """
        Добавление информации о Windows в файл payload.json.
        Использует общий Lock для синхронизации доступа к файлу.
        """
        try:
            payload = windows_info.to_json_compatible()
            file_path = os.path.join(self.script_dir, 'payload.json')

            with self.file_lock:
                logging.debug(f"Воркер {self.worker_id} захватил блокировку файла")

                if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        if not isinstance(data, list):
                            data = []
                    except (json.JSONDecodeError, FileNotFoundError):
                        data = []
                else:
                    data = []

                data.append(payload)

                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)

                logging.debug(f"Воркер {self.worker_id} отпускает блокировку файла")

            logging.info(f"Воркер {self.worker_id} добавил запись в {file_path} (всего записей: {len(data)})")

        except Exception as e:
            logging.error(f"Ошибка сохранения файла: {e}")
            raise

    def stop(self):
        """Остановка воркера"""
        self.running = False
        if self.active_task:
            logging.info(f"Воркер {self.worker_id} прерывает задачу {self.active_task.task_id}")


class InventoryService:
    """
    Сервис инвентаризации - управляет пулом воркеров
    """

    def __init__(self, registry_reader, workers_count: int = 1, script_dir: str = None):
        """
        Args:
            registry_reader: Читатель реестра
            workers_count: Количество воркеров
            script_dir: Директория скрипта
        """
        self.registry_reader = registry_reader
        self.script_dir = script_dir or os.getcwd()
        self.workers_count = workers_count

        self.task_queue = Queue(maxsize=100)

        self.workers: List[InventoryWorker] = []

        self.result_callback = None

        self.tasks_received = 0
        self.tasks_dispatched = 0
        self.stats_lock = Lock()

        self.file_lock = Lock()

        logging.info(f"InventoryService инициализирован: workers={workers_count}")

    def set_result_callback(self, callback):
        """Установка callback для отправки результатов"""
        self.result_callback = callback

    def start(self):
        """Запуск всех воркеров"""
        for i in range(self.workers_count):
            worker = InventoryWorker(
                worker_id=i + 1,
                registry_reader=self.registry_reader,
                script_dir=self.script_dir,
                task_queue=self.task_queue,
                result_callback=self._on_result,
                file_lock=self.file_lock
            )
            worker.start()
            self.workers.append(worker)

        logging.info(f"Запущено {self.workers_count} воркеров")

    def stop(self):
        """Остановка всех воркеров"""
        for worker in self.workers:
            worker.stop()

        for worker in self.workers:
            worker.join(timeout=2.0)

        self._clear_queue()

        logging.info("Все воркеры остановлены")

    def _clear_queue(self):
        """Очистка очереди задач"""
        remaining = 0
        while not self.task_queue.empty():
            try:
                self.task_queue.get_nowait()
                self.task_queue.task_done()
                remaining += 1
            except:
                break

        if remaining > 0:
            logging.warning(f"При остановке удалено необработанных задач: {remaining}")

    def add_task(self, task: Task) -> bool:
        """
        Добавить задачу во внутреннюю очередь сервиса

        Returns:
            bool: True, если задача добавлена
        """
        try:
            self.task_queue.put(task, block=False)

            with self.stats_lock:
                self.tasks_received += 1

            queue_size = self.task_queue.qsize()
            logging.debug(f"Задача {task.task_id} добавлена в очередь сервиса (очередь: {queue_size}, свободных воркеров: {self._get_free_workers_count()})")
            return True

        except Exception as e:
            logging.error(f"Ошибка добавления задачи {task.task_id} в очередь: {e}")
            return False

    def _get_free_workers_count(self) -> int:
        """Подсчитывает количество свободных воркеров"""
        busy = sum(1 for w in self.workers if w.active_task is not None)
        return self.workers_count - busy

    def _on_result(self, result: Result):
        """
        Обработка результата от воркера
        Передает результат обратно в диспетчер
        """
        with self.stats_lock:
            self.tasks_dispatched += 1

        if self.result_callback:
            self.result_callback(result)

    def get_queue_size(self) -> int:
        """Размер внутренней очереди"""
        return self.task_queue.qsize()

    def get_stats(self) -> dict:
        """Возвращает статистику сервиса"""
        with self.stats_lock:
            return {
                'tasks_received': self.tasks_received,
                'tasks_dispatched': self.tasks_dispatched,
                'queue_size': self.task_queue.qsize(),
                'active_workers': self._get_free_workers_count(),
                'total_workers': self.workers_count
            }