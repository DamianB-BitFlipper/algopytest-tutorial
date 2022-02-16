# Unit Testing Algorand Smart Contracts with AlgoPytest

## Overview

This tutorial will cover how to use [AlgoPytest](https://github.com/DamianB-BitFlipper/algopytest), an Algorand-sepcific Pytest plugin, to write a comprehensive test suite for a stateful Algorand Smart Contract. The test suite of a project serves to ensure that the code behaves as expected and flags and deviant behavior.

The smart contract in this tutorial is the same as the one in the "[Using the TEAL Debugger to Debug a Smart Contract](https://developer.algorand.org/tutorials/using-the-teal-debugger-to-debug-a-smart-contract/)" tutorial. However, instead of debugging the buggy smart contract in the tutorial, we will use AlgoPytest to write a test suite which fails because of the bug.

The smart contract is written in PyTEAL.

## Requirements

- A working Algorand `sandbox` instance
- Knowledge of PyTEAL and the Python Algorand SDK
- Basic knowledge of Pytest and test fixtures

## Getting Started

All code of this tutorial is open-source and available in full on [GitHub](https://github.com/DamianB-BitFlipper/algopytest-tutorial).

Firstly, let's start up the Algorand `sandbox` instance and make sure that it is running properly. Instructions for installing the `sandbox` may be found [here](https://github.com/algorand/sandbox#getting-started) . In this tutorial, we will run the test suite on the `release` local testnet. You may adjust this whichever way to suite your needs.

```bash
cd /path/to/installation/of/sandbox/
./sandbox up release
./sandbox status
```

Next, let's install `AlgoPytest`. That is as simple as:

```bash
pip install algopytest-framework
```

There are a few more steps to set up AlgoPytest, but before that, we must first understand the smart contract to be tested.

## (Buggy) Smart Contract

As mentioned previously, this smart contract is identical to the one in the "[Using the TEAL Debugger to Debug a Smart Contract](https://developer.algorand.org/tutorials/using-the-teal-debugger-to-debug-a-smart-contract/)" tutorial. The smart contract records an owner address (the creator) during initialization. It then keeps track of a counter value. Whenever the owner receives a transaction with >= 10 Algos, the counter will be incremented. Otherwise, it will be decremented. This functionality is executed as a group transaction where the first transaction is the payment to the owner and the second, the call to the smart contract.

```python
from pyteal import *

var_owner = Bytes("owner")
var_counter = Bytes("counter")

def buggy_program():
    """
    This is a stateful smart contract with a purposeful bug.
    It is used to demonstrate using the debugger to uncover the bug.
    """
    init_contract = Seq([
        App.globalPut(var_owner, Txn.sender()),
        App.globalPut(var_counter, Int(0)),
        Return(Int(1))
    ])

    is_owner = Txn.sender() == App.globalGet(var_owner)

    # Assign the transactions to variables
    payment_txn = Gtxn[0]
    app_txn = Txn # This transaction is at index 1

    payment_check = payment_txn.type_enum() == TxnType.Payment
    payment_receiver_check = payment_txn.receiver() == App.globalGet(var_owner)
    app_check = app_txn.type_enum() == TxnType.ApplicationCall

    group_checks = And(
        payment_check,
        payment_receiver_check,
        app_check,
    )

    counter = App.globalGet(var_counter)
    increment_counter  = Seq([
        Assert(group_checks),
        # Increment the counter if the sender sends the owner more than 10 Algos.
        # Otherwise decrement the counter
        If(payment_txn.amount() >= Int(10 * 1000000),
           App.globalPut(var_counter, counter + Int(1)),
           App.globalPut(var_counter, counter - Int(1)),
        ),

        Return(Int(1))
    ])

    program = Cond(
        [Txn.application_id() == Int(0), init_contract],
        [Txn.on_completion() == OnComplete.DeleteApplication, Return(is_owner)],
        [Txn.on_completion() == OnComplete.UpdateApplication, Return(is_owner)],
        [Txn.on_completion() == OnComplete.OptIn, Return(Int(1))],
        [Txn.on_completion() == OnComplete.CloseOut, Return(Int(1))],
        [Txn.on_completion() == OnComplete.NoOp, increment_counter],
    )

    return program

if __name__ == "__main__":
    print(compileTeal(buggy_program(), Mode.Application))
```

This stateful smart contract has two important code blocks `init_contract` and `increment_counter`. 

The `init_contract` block is called during contract deployment and simply initializes the owner and counter global variables.
```python
init_contract = Seq([
    App.globalPut(var_owner, Txn.sender()),
    App.globalPut(var_counter, Int(0)),
    Return(Int(1))
])
```

The `increment_counter` block is executed during any normal application call. It performs the logic which checks if the owner is receiving more or less than 10 Algos and increments/decrements the counter respectively.

It begins by checking the structure of the group transaction, that the first transaction is a payment transaction to the owner and that the second transaction is an application call to this smart contract.
```python
# Assign the transactions to variables
payment_txn = Gtxn[0]
app_txn = Txn # This transaction is at index 1

payment_check = payment_txn.type_enum() == TxnType.Payment
payment_receiver_check = payment_txn.receiver() == App.globalGet(var_owner)
app_check = app_txn.type_enum() == TxnType.ApplicationCall

group_checks = And(
    payment_check,
    payment_receiver_check,
    app_check,
)
```

Second, it performs the increment/decrement accordingly.

```python
counter = App.globalGet(var_counter)
increment_counter  = Seq([
    Assert(group_checks),
    # Increment the counter if the sender sends the owner more than 10 Algos.
    # Otherwise decrement the counter
    If(payment_txn.amount() >= Int(10 * 1000000),
       App.globalPut(var_counter, counter + Int(1)),
       App.globalPut(var_counter, counter - Int(1)),
    ),

    Return(Int(1))
])
```

There is a bug in this smart contract. We will use AlgoPytest to write a test suite which should fail because of this bug. Then once we patch this bug in the smart contract, all of the unit tests should pass.

## Writing the Test Suite

There are two components when it comes to writing an AlgoPytest-enabled test suite. The first component is the setup and initialization. The second component are the actual tests themselves.

As this ultimately is a Pytest test suite with AlgoPytest as an installed plugin, we must follow the directory structure expected by Pytest. More details on that [here](https://docs.pytest.org/en/6.2.x/goodpractices.html#choosing-a-test-layout-import-rules). Essentially, all Pytest related code must be found with a `tests` directory in the root of the project. Setup code including the initialization code of AlgoPytest is found within a `conftest.py` file. Test cases are written in files with filenames beginning with `test_`.

```bash
mkdir tests
cd tests
touch conftest.py test_deployment.py
```

The structure of this [project](https://github.com/DamianB-BitFlipper/algopytest-tutorial) outlines this directory strcture.

```bash
.
├── artifacts
├── assets
│   ├── approval_program.py
│   ├── bugfree_approval_program.py
│   └── clear_program.py
├── README.md
└── tests
    ├── conftest.py
    └── test_deployment.py
```

### Setting Up AlgoPytest
