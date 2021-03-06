from algopytest import initialize

# Load the smart contracts from this project. The path to find these
# imports is set by the environment variable `$PYTHONPATH`.
from approval_program import buggy_program
from clear_program import clear_program

def pytest_configure(config):
    """Initialize algopytest before the pytest tests run."""
    initialize(approval_program=buggy_program, 
               clear_program=clear_program,
               global_ints=1, global_bytes=1)

