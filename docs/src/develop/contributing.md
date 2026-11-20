# Contribution Guidelines for Abilian SBE

Thank you for your interest in contributing to Abilian SBE! We value the contributions of each member of the community and strive to create an environment where everyone can engage productively and respectfully. As part of the Abilian SBE community, all participants are expected to act with courtesy and professionalism at all times.

## Ways to Contribute

There are many ways to get involved and contribute to the project:

- **Submit Bug Reports and Feature Requests:** Use the [GitHub Issues page](https://github.com/abilian/abilian-sbe-monorepo/issues) to report bugs or propose new features. Please ensure your reports are clear and detailed. We welcome any feedback or enhancement suggestions, and they can also be discussed via the project's mailing list.
- **Improve [Documentation](https://github.com/abilian/abilian-sbe-monorepo/tree/main/docs):** Help us enhance and clarify the documentation to ensure it is accurate and easy to understand.
- **Submit [Pull Requests](https://github.com/abilian/abilian-sbe-monorepo/pulls):** Propose changes to the codebase or documentation by submitting pull requests (PRs). We encourage you to include both tests and documentation with your code to ensure a smooth review process.

## Architecture Decision Records (ADRs)

A significant part of shaping the future of Abilian SBE involves participating in the review and creation of **[Architecture Decision Records](https://github.com/abilian/abilian-sbe-monorepo/tree/main/notes/adrs) (ADRs)**. These documents capture major architectural decisions and guide the project’s long-term technical direction. Contributions that involve new features or significant changes should refer to, or propose, an ADR to ensure structured and transparent decision-making. Please consult the existing ADRs before suggesting changes that may affect the project’s architecture.

## Code Contribution Process

1. **Fork and Clone the Repository:** Begin by forking the repository and cloning it to your local environment for development.

2. **Create a New Branch:** Work on a dedicated branch for your changes. Use a descriptive branch name that reflects the issue or feature you are addressing.

3. **Follow Code Conventions:**
   - Adhere to the project’s coding standards, including style, formatting, and clean code practices. Contributions should follow [PEP-8](https://peps.python.org/pep-0008/) guidelines where applicable.
   - An [EditorConfig](https://editorconfig.org/) file is available in the repository to help ensure consistent code style. Make sure your IDE supports it.
   - Format your code using `make format` for consistent styling.

4. **Add Tests:** If your contribution adds new functionality, include unit tests to ensure the code behaves as expected. Tests should be located in the appropriate `tests` sub-folder.

5. **Check Existing Issues and PRs:** Before submitting your changes, verify if there are any existing issues or PRs related to the same problem to avoid duplication.

6. **Write Meaningful Commit Messages:** Ensure your commit messages clearly describe the changes made. Reference any relevant issue or PR numbers.

7. **Run Tests and Linting:** Make sure that all tests pass and that your code complies with the project’s linting standards.

8. **Update Documentation:** If your changes affect the user-facing aspects of the project, update the corresponding documentation. For new features, add documentation to the appropriate `docs` subfolder. Documentation is compiled with [Sphinx](https://www.sphinx-doc.org/) and supports reStructuredText and Markdown via the [MyST](https://myst-parser.readthedocs.io/) extension.

9. **Submit the PR:** Push your changes to your fork and open a pull request. In your PR description, explain the purpose of the changes and include any relevant issue numbers.

10. **Engage in Code Review:** Once your PR is submitted, maintainers will review your changes. Be open to feedback and be prepared to make revisions if necessary.

## Code Style

- **Python Compatibility:** Ensure your code is compatible with Python 3.10+.
- **Type Annotations:** Use type hints wherever possible to improve code clarity and maintainability.
- **Logging:** Use Python’s `logging` module instead of printing debug information.
- **PEP-8 Compliance:** Follow PEP-8, including the use of spaces around operators, 4-space indentation, and line breaks after 110 characters.
- **Imports:** Imports should be placed after module-level documentation and before anything else. Use only necessary imports and remove unused ones.
- **Naming Conventions:** Use `CamelCase` for class names, `snake_case` for methods and variables, and `SNAKE_UPPERCASE` for constants.


## Testing and Documentation

- **Unit Tests:** Tests should be implemented in the appropriate `tests` subfolders and written using `pytest`.
- **Documentation Contributions:** Ensure any new feature or change is documented, either by updating existing documents or creating new ADRs in the `notes/adrs` folder.

## License Compliance

All contributions must comply with the project’s license. By contributing code, you agree that your contributions will be released under this license.

## Questions or Suggestions

If you have questions, suggestions, or need help contributing, feel free to open an issue in the repository or discuss via the project’s mailing list. We're happy to assist.

Thank you again for your interest in contributing to Abilian SBE. Your input helps make the project better, and we look forward to collaborating with you!
