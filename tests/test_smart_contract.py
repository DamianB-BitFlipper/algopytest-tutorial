import pytest

import algosdk
from algosdk.future import transaction

from algopytest import (
    create_app,
    delete_app,
    update_app,
    opt_in_app, 
    close_out_app,
    clear_app,
    call_app,
    payment_transaction,
    application_global_state,
    group_elem,
    group_transaction,
)

# Constants

# Convenience conversion where one Algorand is 10e6 microAlgos
ALGO = 1000000

# Pytest Fixtures

@pytest.fixture
def user1_in(user1, smart_contract_id):
    """Create a ``user1`` fixture that has already opted in to ``smart_contract_id``."""
    opt_in_app(user1, smart_contract_id)

    # The test runs here
    yield user1

    # Clean up by closing out of the application
    close_out_app(user1, smart_contract_id)

# Pytest tests

def test_initialization(owner, smart_contract_id):
    # Read the registrar's address from the application's global state
    ret = application_global_state(
        smart_contract_id,
        address_fields=['owner'],
    )
    
    # Assert that the global fields were set properly
    assert ret['owner'] == owner.address
    assert ret['counter'] == 0

def test_delete_application_from_owner(owner):
    app_id = create_app(owner)
    delete_app(owner, app_id)

def test_delete_application_from_nonowner(user1, smart_contract_id):
    # Expect an exception
    with pytest.raises(algosdk.error.AlgodHTTPError):
        delete_app(user1, smart_contract_id)

def test_update_from_owner(owner, smart_contract_id):
    # Should not raise an exception
    update_app(owner, smart_contract_id)

def test_update_from_nonowner(user1, smart_contract_id):
    # Expect an exception
    with pytest.raises(algosdk.error.AlgodHTTPError):
        update_app(user1, smart_contract_id)

@pytest.mark.parametrize(
    "users", 
    [
        ['owner'],
        ['owner', 'user1'],
        ['user1'], # Test a non-owner opt in
        ['user1', 'owner'], # Test when a non-owner opts in before the owner
        ['user1', 'owner', 'user2'],
    ],
)
@pytest.mark.parametrize(
    "opt_out_fn",
    [
        close_out_app,
        clear_app,
    ]
)
def test_opt_in_out(request, users, opt_out_fn, smart_contract_id):
    # Convert the string fixture names to the actual fixtures
    users = list(map(lambda user: request.getfixturevalue(user), users))

    # Opt in going forward through `users`
    for user in users:
        opt_in_app(user, smart_contract_id)

    # Close out going backwards through `users`
    for user in reversed(users):
        opt_out_fn(user, smart_contract_id)

def test_increment_counter(owner, user1_in, smart_contract_id):

    # Call the application with a payment transaction in position 0
    # The `counter` gets incremented if the amount sent is >= 10 Algos
    group_transaction(
        group_elem(payment_transaction)(user1_in, owner, 10 * ALGO),
        group_elem(call_app)(user1_in, smart_contract_id),
    )

    # Read the `counter` to check its value
    ret = application_global_state(
        smart_contract_id,
        address_fields=['owner'],
    )
    assert ret['counter'] == 1

@pytest.mark.parametrize(
    "operations",
    [
        ['+'],
        ['+', '+'],
        ['+', '-'],
        ['+', '+', '-', '+', '-', '-'],
        ['+', '-', '-', '+'],
    ],
)
def test_serial_operations(owner, user1_in, operations, smart_contract_id):
    # Create the functions to be dispatch during increment and decrement operations
    def _increment():
        # Send 10 Algos to signal an increment operation
        group_transaction(
            group_elem(payment_transaction)(user1_in, owner, 10 * ALGO),
            group_elem(call_app)(user1_in, smart_contract_id),
        )

    def _decrement():
        # Send fewer than 10 Algos to signal a decrement operation
        group_transaction(
            group_elem(payment_transaction)(user1_in, owner, 10 * ALGO - 1),
            group_elem(call_app)(user1_in, smart_contract_id),
        )

    counter = 0
    for op in operations:
        # Dispatch the respective functions
        if op == '+':
            _increment()
            counter += 1
        elif op == '-':
            _decrement()
            counter -= 1
        else:
            raise ValueError(f"Undefined operation: {op}")

        # Check the `counter` correctness
        ret = application_global_state(
            smart_contract_id,
            address_fields=['owner'],
        )
        assert ret['counter'] == counter
