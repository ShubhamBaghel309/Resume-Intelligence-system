from fastmcp import FastMCP
from typing import Annotated
from pydantic import Field

mcp = FastMCP("CalculatorMCP")

@mcp.tool()
def calculate(
    operation: Annotated[str | None, Field(description="Operation: 'add', 'subtract', 'multiply', or 'divide'")] = None,
    a: Annotated[float | None, Field(description="First number (e.g., 10, 3.5)")] = None,
    b: Annotated[float | None, Field(description="Second number (e.g., 5, 2.0)")] = None,
) -> dict:
    """Perform basic arithmetic between two numbers."""
    missing = []
    if not operation: missing.append("operation")
    if a is None: missing.append("a")
    if b is None: missing.append("b")
    if missing:
        return {"status": "missing_fields", "missing_fields": missing, "message": f"Missing: {', '.join(missing)}"}

    op = operation.strip().lower()
    if op == "add":
        result = a + b
        expr = f"{a} + {b}"
    elif op == "subtract":
        result = a - b
        expr = f"{a} - {b}"
    elif op == "multiply":
        result = a * b
        expr = f"{a} x {b}"
    elif op == "divide":
        if b == 0:
            return {"status": "error", "message": "Cannot divide by zero."}
        result = a / b
        expr = f"{a} / {b}"
    else:
        return {"status": "error", "message": f"Unknown operation '{operation}'. Use: add, subtract, multiply, divide"}

    return {"status": "success", "message": f"{expr} = {result}", "result": result}

if __name__ == "__main__":
    mcp.run()
