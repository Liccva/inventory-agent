"""
Управление очередями задач и результатов
"""
import logging
from queue import Queue, Full, Empty
from typing import Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import uuid
from datetime import datetime


class TaskStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Task:
    """Задача для выполнения"""
    task_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    command: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    status: TaskStatus = TaskStatus.PENDING
    data: Any = None

    @classmethod
    def create(cls, command: str, data: Any = None):
        return cls(command=command, data=data)


@dataclass
class Result:
    """Результат выполнения задачи"""
    task_id: str
    command: str
    status: TaskStatus
    result: Any = None
    error: Optional[str] = None
    completed_at: str = field(default_factory=lambda: datetime.now().isoformat())

    @classmethod
    def success(cls, task: Task, result_data: Any):
        return cls(
            task_id=task.task_id,
            command=task.command,
            status=TaskStatus.COMPLETED,
            result=result_data
        )

    @classmethod
    def failure(cls, task: Task, error_msg: str):
        return cls(
            task_id=task.task_id,
            command=task.command,
            status=TaskStatus.FAILED,
            error=error_msg
        )


class QueueManager:
    """
    Менеджер очередей - интерфейс для работы с очередями
    """

    def __init__(self, maxsize: int = 100):
        self.maxsize = maxsize
        self.task_queue = Queue(maxsize=maxsize)
        self.result_queue = Queue(maxsize=maxsize)

        # Статистика
        self.tasks_added = 0
        self.tasks_completed = 0
        self.tasks_failed = 0

        logging.info(f"QueueManager инициализирован (maxsize={maxsize})")

    def add_task(self, task: Task) -> bool:
        """Добавить задачу в очередь"""
        try:
            self.task_queue.put(task, block=False)
            self.tasks_added += 1
            return True
        except Full:
            logging.error(f"Очередь задач переполнена. Задача {task.task_id} не добавлена")
            return False

    def get_task(self) -> Optional[Task]:
        """Получить задачу из очереди (для диспетчера)"""
        try:
            task = self.task_queue.get(block=False)
            task.status = TaskStatus.PROCESSING
            return task
        except Empty:
            return None

    def task_done(self):
        """Отметить задачу как обработанную"""
        self.task_queue.task_done()

    def add_result(self, result: Result) -> bool:
        """Добавить результат в очередь"""
        try:
            self.result_queue.put(result, block=False)
            if result.status == TaskStatus.COMPLETED:
                self.tasks_completed += 1
            else:
                self.tasks_failed += 1
            return True
        except Full:
            logging.error(f"Очередь результатов переполнена. task_id={result.task_id}")
            return False

    def get_result(self) -> Optional[Result]:
        """Получить результат из очереди"""
        try:
            return self.result_queue.get(block=False)
        except Empty:
            return None

    def result_done(self):
        """Отметить результат как обработанный"""
        self.result_queue.task_done()

    def get_stats(self) -> dict:
        return {
            'tasks_added': self.tasks_added,
            'tasks_completed': self.tasks_completed,
            'tasks_failed': self.tasks_failed,
            'task_queue_size': self.task_queue.qsize(),
            'result_queue_size': self.result_queue.qsize()
        }