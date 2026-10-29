"""
Backward-compatible wrapper for minimax_test_e2e.py.
Redirects execution to e2e_tests/minimax_test_e2e.py.
"""
import sys
import os

if __name__ == "__main__":
    test_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "e2e_tests", "minimax_test_e2e.py")
    with open(test_path, "r", encoding="utf-8") as f:
        code = compile(f.read(), test_path, "exec")
        exec(code, {"__name__": "__main__", "__file__": test_path})
