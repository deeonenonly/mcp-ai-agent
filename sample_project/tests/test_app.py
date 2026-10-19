
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from app import calculate_total, apply_discount


def test_calculate_total():
    assert calculate_total(100, 3) == 300


def test_calculate_total_zero_quantity():
    assert calculate_total(100, 0) == 0


def test_apply_discount():
    assert apply_discount(200, 10) == 180


def test_apply_zero_discount():
    assert apply_discount(200, 0) == 200
