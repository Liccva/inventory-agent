# Windows Inventory Agent

Агент для сбора информации об ОС Windows по команде `inventory`. Работает в многопоточном режиме с использованием очередей.

## Требования

- Python 3.7 или выше
- ОС Windows (доступ к реестру)

## Установка

1. Клонируйте репозиторий:
```bash
git clone <url>
cd inventory-agent
```
2. Создайте venv (опционально)

```bash
python -m venv venv
venv\Scripts\activate 
```

3. Установка зависимостей не требуется (используется только стандартная библиотека).

## Конфигурация

Создайте файл config.ini в директории со скриптом:

```ini
[logging]
level = info
log_path = data\

[workers]
InventoryWorkers = 1
```
Параметры:

- level — уровень логирования (debug, info, warning, error)
- log_path — директория для файла log.txt
- InventoryWorkers — количество параллельных воркеров

## Использование

Создайте файл с командами (например, commands.txt):

```text
inventory
audit
install 7zip
inventory
reboot
```
Запустите агент:

```bash
python agent.py commands.txt
```
## Результат 
payload.json:
```json
[
  {
    "os": {
      "ProductName": "Windows 10 Home",
      "CurrentBuild": "22631",
      "DisplayVersion": "23H2",
      "EditionID": "CoreSingleLanguage"
    }
  }
]
```

Логи сохраняются в data/log.txt (путь настраивается).

