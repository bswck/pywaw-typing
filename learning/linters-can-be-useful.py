# ruff check learning/linters-can-be-useful.py --select=RUF
# This is a silly example with a memory leak!


class Logger:
    logs: list[str] = []

    @classmethod
    def log_message(cls, message: str) -> None:
        cls.logs.append(message)


Logger.log_message("System initialized.")
Logger.log_message("User logged in.")
print(Logger.logs)
