"""Плагин калькулятора"""
import re
import math

def run(query: str, context: dict) -> str:
    # Извлекаем выражение
    expr = query.lower()
    for w in ["посчитай", "вычисли", "сколько будет", "калькулятор", "чему равно"]:
        expr = expr.replace(w, "")
    expr = expr.strip()
    # Заменяем русские операторы
    expr = expr.replace("плюс", "+").replace("минус", "-")
    expr = expr.replace("умножить на", "*").replace("разделить на", "/")
    expr = expr.replace("в степени", "**").replace("корень из", "math.sqrt")
    # Оставляем только безопасные символы
    safe = re.sub(r"[^0-9+\-*/().^ mathsqrlog]", "", expr)
    try:
        result = eval(safe, {"__builtins__": {}, "math": math, "sqrt": math.sqrt})
        return f"🧮 {expr.strip()} = **{result}**"
    except Exception:
        return f"Не смог вычислить: {expr}"
