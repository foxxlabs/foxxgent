# Contributing to FoxxGent

Thank you for your interest in contributing to FoxxGent! We welcome contributions from the community and appreciate your help in making this project better.

## How to Contribute

### 1. Fork the Repository

Click the "Fork" button on the GitHub repository to create your own copy of the project.

### 2. Clone Your Fork

```bash
git clone https://github.com/YOUR_USERNAME/foxxgent.git
cd foxxgent
```

### 3. Create a Feature Branch

Create a new branch for your changes:

```bash
git checkout -b feature/your-feature-name
# or for bug fixes:
git checkout -b fix/your-bug-fix
```

### 4. Make Your Changes

Implement your feature or bug fix. Ensure your code follows the project's coding standards.

### 5. Commit Your Changes

Follow the commit message conventions below:

```bash
git add .
git commit -m "feat: add new feature description"
```

### 6. Push to Your Fork

```bash
git push origin feature/your-feature-name
```

### 7. Create a Pull Request

Open a pull request from your fork to the main repository. Fill out the PR template with all relevant details.

## Code Style Guidelines

### Python (PEP 8)

- Use 4 spaces for indentation
- Maximum line length of 100 characters
- Use meaningful variable and function names
- Follow PEP 8 naming conventions:
  - `snake_case` for functions and variables
  - `CamelCase` for classes
  - `UPPER_CASE` for constants

### Type Hints

Always use type hints for function signatures:

```python
def process_user(user_id: int, name: str) -> dict[str, Any]:
    """Process user data with type hints."""
    return {"id": user_id, "name": name}
```

### General Guidelines

- Keep functions small and focused
- Add docstrings to public functions
- Handle exceptions appropriately
- Avoid hardcoded values - use configuration instead
- Write tests for new functionality

## Development Environment Setup

### Prerequisites

- Python 3.10 or higher
- pip or poetry

### 1. Clone and Setup

```bash
git clone https://github.com/foxxgent/foxxgent.git
cd foxxgent
```

### 2. Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment

```bash
cp .env.example .env
# Edit .env with your API keys
```

### 5. Run Development Server

```bash
python main.py
```

The server will start at `http://localhost:8000`.

## Running Tests

If tests are available in the project, run them with:

```bash
pytest
# or with coverage:
pytest --cov=. --cov-report=html
```

For specific test files:

```bash
pytest tests/test_file.py
```

## Submitting Features vs Bug Fixes

### Bug Fixes

1. Create an issue describing the bug
2. Fork the repo and create a fix branch
3. Add a test that reproduces the bug
4. Fix the bug and ensure all tests pass
5. Submit a PR with `fix:` prefix in the commit message

### New Features

1. Open an issue to discuss the feature first
2. Get feedback from maintainers before starting work
3. Create a feature branch
4. Implement the feature with tests
5. Update documentation if needed
6. Submit a PR with `feat:` prefix in the commit message

## Commit Message Conventions

Use conventional commits format:

| Type | Description |
|------|-------------|
| `feat:` | New feature |
| `fix:` | Bug fix |
| `docs:` | Documentation changes |
| `style:` | Code style changes (formatting, no logic change) |
| `refactor:` | Code refactoring |
| `test:` | Adding or updating tests |
| `chore:` | Maintenance tasks |

### Examples

```
feat: add Gmail integration support
fix: resolve Telegram pairing timeout issue
docs: update API endpoint documentation
refactor: simplify agent brain logic
test: add unit tests for exec_tools
```

## Pull Request Template

When submitting a pull request, please include:

```markdown
## Description
Brief description of what this PR does.

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Documentation update
- [ ] Refactoring
- [ ] Other

## Testing
Describe testing performed:
- [ ] Unit tests added/updated
- [ ] Manual testing completed
- [ ] No testing needed

## Checklist
- [ ] Code follows style guidelines
- [ ] Type hints added/updated
- [ ] Documentation updated (if applicable)
- [ ] Tests pass
- [ ] No breaking changes (or documented)
```

## Code of Conduct

This project follows the [GitHub Community Code of Conduct](https://github.com/github/code-of-conduct/blob/main/code-of-conduct.md). By participating, you are expected to uphold this code.

## License

By contributing to FoxxGent, you agree that your contributions will be licensed under the [MIT License](LICENSE).

---

Thank you for contributing to FoxxGent!
