---
name: improve-tests
description: Consolidate tests down to core cases for maintainability
argument-hint: "[test file/scope]"
---
Cut down tests to the core test cases to make the test file easier to maintain and less fragile.

Review and consolidate tests to those that target core functionality. Test only against the public contract of the module/class and observable outputs (including e.g. logging, errors). Never test internal implementation details. 

If the test relies on an extensive amount of mocking, to the point where it heavily depends on external resources or implementation details of other functions/libraries - consider omitting the test altogether.
