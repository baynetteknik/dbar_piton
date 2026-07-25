"""Unit tests for FormulaService AST evaluator."""

import pytest
from src.desktop.services.formula_service import FormulaSecurityError, FormulaService


def test_formula_service_arithmetic():
    """Test standard arithmetic operations."""
    row = {"alacak": 1500.0, "borç": 500.0}
    # alacak - borç
    res = FormulaService.evaluate("alacak - borç", row)
    assert res == 1000.0

    # (borç / (alacak + borç)) * 100
    res_ratio = FormulaService.evaluate("(borç / (alacak + borç)) * 100", row)
    assert pytest.approx(res_ratio, 0.01) == 25.0


def test_formula_service_zero_division():
    """Test division by zero returns 0.0 without crashing."""
    row = {"alacak": 0.0, "borç": 0.0}
    res = FormulaService.evaluate("borç / alacak", row)
    assert res == 0.0


def test_formula_service_safe_functions():
    """Test whitelist functions like abs, round, min, max."""
    row = {"val1": -45.678, "val2": 12.3}
    assert FormulaService.evaluate("abs(val1)", row) == 45.678
    assert FormulaService.evaluate("round(val1, 2)", row) == -45.68
    assert FormulaService.evaluate("min(val1, val2)", row) == -45.678
    assert FormulaService.evaluate("max(val1, val2)", row) == 12.3


def test_formula_service_security():
    """Test that unsafe node types like __import__ or open raise FormulaSecurityError."""
    row = {"x": 1}
    with pytest.raises(FormulaSecurityError):
        FormulaService.evaluate("__import__('os').system('dir')", row)
