# ruff check staying-updated/old-code-fixed.py --select=UP,I,F --unsafe-fixes --fix

from __future__ import annotations

import collections
import dataclasses
import enum
import functools
import operator
import random
import sys
from typing import (
    Any,
    Callable,
    Deque,
    NamedTuple,
    Optional,
    Self,
    Tuple,
    TypeAlias,
    Union,
)


UnaryEval: TypeAlias = Callable[[int], int]
BinaryEval: TypeAlias = Callable[[int, int], int]


class OperationSchema(NamedTuple):
    eval: UnaryEval | BinaryEval
    quantity_range: range


Range: TypeAlias = tuple[int, int]
Registry: TypeAlias = "dict[int, Level]"
OperationMapping: TypeAlias = "dict[str, OperationSchema]"
Handler: TypeAlias = "Callable[[str], Tuple[ResultStatus, Any]]"


@functools.total_ordering
class Level:
    _registry: Registry = {}
    _id: int
    _description: Optional[str]
    _range: Range
    _operations: OperationMapping

    @property
    def id(self) -> int:
        return self._id

    @property
    def description(self) -> Optional[str]:
        description = self._description
        if description is not None:
            description %= self.range
        return description

    @property
    def range(self) -> Range:
        return self._range

    @property
    def operations(self) -> OperationMapping:
        return self._operations

    @classmethod
    def get(cls, level_id: int) -> Optional[Level]:
        return cls.registry().get(level_id)

    @staticmethod
    def set(level: Level) -> Level:
        Level._registry[level.id] = level
        return level

    @staticmethod
    def registry() -> Registry:
        return Level._registry.copy()

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Level):
            return self.id == other.id
        return NotImplemented

    def __lt__(self, other: object) -> bool:
        if isinstance(other, Level):
            return self.id < other.id
        return NotImplemented

    def __str__(self) -> str:
        return str(self.id)

    def __init_subclass__(cls, **kw: Any) -> None:
        level_id: Optional[int] = kw.get("id")
        if level_id is None:
            return
        cls._id = level_id
        if level_id in Level.registry():
            raise ValueError(
                f"level {level_id!r} has already been registered and cannot be "
                "overriden"
            )
        Level.set(cls())


class Simple(Level, id=1):
    _description = "simple operations with numbers %s-%s"
    _range = (2, 9)
    _operations = {
        "+": OperationSchema(operator.add, range(2)),
        "-": OperationSchema(operator.sub, range(2)),
        "*": OperationSchema(operator.mul, range(2)),
    }


class IntegralSquares(Level, id=2):
    _description = "integral squares of %s-%s"
    _range = (11, 29)
    _operations = {"": OperationSchema(lambda x: x**2, range(1))}


@dataclasses.dataclass
class Task:
    operands: Tuple[int, ...]
    operation: str
    level: Level

    @property
    def operations(self) -> OperationMapping:
        return self.level.operations

    @property
    def solution(self) -> int:
        eval_, quantity_range = self.operations[self.operation]
        if len(self.operands) - 1 not in quantity_range:
            raise ValueError("number of operands out of range")
        solution = eval_(*self.operands)
        return solution

    @classmethod
    def random(
        cls,
        operand_range: Optional[Tuple[int, int]] = None,
        level: Level = Level.get(1),  # type: ignore[assignment]
    ) -> Self:
        if operand_range is None:
            operand_range = level.range
        operation_symbol, operation = random.choice(tuple(level.operations.items()))
        return cls(
            operands=tuple(
                random.randint(*operand_range)
                for _ in range(operation.quantity_range.stop)
            ),
            operation=operation_symbol,
            level=level,
        )

    def __repr__(self) -> str:
        operands = map(str, self.operands)
        if self.operation:
            operation = " " + self.operation + " "
        else:
            operation = " "
        return operation.join(operands)


class ResultStatus(enum.IntEnum):
    ok = 0
    error = 1
    exit = 2


class FailurePolicy(enum.IntEnum):
    reenter = 0
    ignore = 1


class Comms:
    def __init__(
        self,
        input_text: Optional[str] = None,
        handler: Optional[Handler] = None,
        failure_policy: FailurePolicy = FailurePolicy.reenter,
    ) -> None:
        if input_text is None:
            input_text = ""
        self.default_input_text = input_text
        self.default_handler = handler
        self.failure_policy = failure_policy

    def input(
        self,
        message: object = None,
        text: Optional[str] = None,
        handler: Optional[Handler] = None,
        reenter_message_repeat: bool = True,
    ) -> Any:
        if message is not None:
            print(message)
        text = text or self.default_input_text
        handler = handler or self.default_handler
        resp = res = input(text)
        if callable(handler):
            msg = None
            try:
                status, res = handler(resp)
            except Exception as exc:
                status = ResultStatus.error
                if exc.args:
                    msg = exc.args[0]
            if status is ResultStatus.exit:
                sys.exit("Exit requested")
            if status is ResultStatus.ok or (
                status is ResultStatus.error
                and self.failure_policy is FailurePolicy.ignore
            ):
                return res
            msg and print(msg)
            if self.failure_policy is FailurePolicy.reenter:
                if not reenter_message_repeat:
                    message = None
                return self.input(message=message, text=text, handler=handler)
        return res


class App:
    def __init__(
        self,
        comms: Comms,
        total_tasks: int,
        level: Optional[Level] = None,
        filename: str = "results.txt",
        done_tasks: Deque[Task] = collections.deque(),
        save_results: Optional[bool] = None,
        score: int = 0,
    ) -> None:
        self.level = level
        self.comms = comms
        self.filename = filename
        self.save_results = save_results
        self.score = score
        self.total_tasks = total_tasks
        self.done_tasks = done_tasks

    @property
    def done(self) -> int:
        return len(self.done_tasks)

    @property
    def pending(self) -> int:
        return self.total_tasks - self.done

    @staticmethod
    def _handle_level_choice(answer: str) -> Tuple[ResultStatus, Optional[Level]]:
        try:
            res = int(answer)
        except ValueError as exc:
            raise ValueError("Incorrect format.") from exc
        if res not in Level.registry():
            raise ValueError(f"Incorrect format.")
        return ResultStatus.ok, Level.get(res)

    @staticmethod
    def _handle_task_solution(task: Task, answer: str) -> Tuple[ResultStatus, bool]:
        if not answer or any(map(str.isalpha, answer)):
            raise ValueError("Wrong format! Try again.")
        solution = int(answer)
        is_right = solution == task.solution
        print("Right!" if is_right else "Wrong!")
        return ResultStatus.ok, is_right

    @staticmethod
    def _handle_save_result_answer(
        answer: str,
    ) -> Tuple[ResultStatus, Union[str, bool]]:
        if answer not in ("yes", "YES", "y", "Yes"):
            return ResultStatus.exit, answer
        return ResultStatus.ok, True

    @staticmethod
    def _handle_name(answer: str) -> Tuple[ResultStatus, str]:
        if not (0 < len(answer) < 36):
            raise ValueError("Incorrect format. Name must be from 1 to 35 characters.")
        return ResultStatus.ok, answer

    def run(self) -> None:
        if self.level is None:
            level_string = "\n".join(
                [
                    f"{level} - {level.description}"
                    for level in Level.registry().values()
                ]
            )
            self.level = self.comms.input(
                "Which level do you want? Enter a number:\n" f"{level_string}",
                handler=self._handle_level_choice,
            )
        while self.pending:
            task = Task.random(level=self.level)
            handler = functools.partial(self._handle_task_solution, task)
            self.score += self.comms.input(task, handler=handler)
            self.done_tasks.append(task)
        if self.save_results is None:
            self.save_results = self.comms.input(
                f"Your mark is {self.score}/{self.total_tasks}. "
                "Would you like to save the result? Enter yes or no.",
                handler=self._handle_save_result_answer,
            )
        if self.save_results:
            name = self.comms.input("What is your name?", handler=self._handle_name)
            line = f"{name}: {self.score}/{self.total_tasks} in level {self.level} ({self.level.description})"
            with open(self.filename, "a+") as file:
                file.write(line)
            print("Results have been saved!")


if __name__ == "__main__":
    app = App(comms=Comms(input_text=""), total_tasks=5)
    app.run()
