"""Runbook-specific exceptions."""


class RunbookFailedError(Exception):
    """Raised when a runbook step expectation fails."""

    def __init__(self, step_name: str, condition: str, message: str):
        self.step_name = step_name
        self.condition = condition
        self.message = message
        super().__init__(self.__str__())

    def __str__(self) -> str:
        return (
            f"\nRunbook Step Failed: {self.step_name}\n"
            f"Condition: {self.condition}\n"
            f"Message: {self.message}\n"
        )


class StepExecutionError(Exception):
    """Raised when an expression cannot be evaluated."""

    def __init__(self, expr: str, original_error: Exception):
        self.expr = expr
        self.original_error = original_error
        super().__init__(f"Error evaluating expression `{expr}`: {original_error}")
