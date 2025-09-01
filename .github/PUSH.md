# Pre-commit Commands for AEGIS

This document outlines the pre-commit commands that should be run before pushing code to the repository to ensure code quality and consistency.

## Required Pre-commit Commands

### 1. Code Formatting with Black
```bash
black . --exclude="/(venv|build|dist)/"
```

### 2. Import Sorting with isort
```bash
isort . --profile black --skip venv --skip build --skip dist
```

### 3. Linting with flake8
```bash
flake8 . --exclude=venv,build,dist --max-line-length=88 --extend-ignore=E203,W503
```

### 4. Security Scanning with Bandit
```bash
bandit -r . -f json -o bandit-report.json --exclude ./venv,./build,./dist
```

### 5. Type Checking with mypy (optional)
```bash
mypy . --ignore-missing-imports --exclude venv --exclude build --exclude dist
```

### 6. Run Unit Tests
```bash
python -m pytest tests/ -v --tb=short
```

### 7. Run Integration Tests
```bash
python -m pytest tests/integration/ -v --tb=short
```


## Pre-commit Hook Setup

To automatically run these commands before each commit, you can set up a pre-commit hook:

1. Install pre-commit:
```bash
pip install pre-commit
```

2. Create a `.pre-commit-config.yaml` file in the repository root:
```yaml
repos:
  - repo: https://github.com/psf/black
    rev: 23.12.1
    hooks:
      - id: black
        exclude: ^(venv|build|dist)/

  - repo: https://github.com/pycqa/isort
    rev: 5.13.2
    hooks:
      - id: isort
        args: ["--profile", "black"]
        exclude: ^(venv|build|dist)/

  - repo: https://github.com/pycqa/flake8
    rev: 7.0.0
    hooks:
      - id: flake8
        args: ["--max-line-length=88", "--extend-ignore=E203,W503"]
        exclude: ^(venv|build|dist)/

  - repo: https://github.com/pycqa/bandit
    rev: 1.7.5
    hooks:
      - id: bandit
        args: ["-r", ".", "-f", "json", "-o", "bandit-report.json"]
        exclude: ^(venv|build|dist)/

  - repo: local
    hooks:
      - id: pytest
        name: pytest
        entry: python -m pytest tests/ -v --tb=short
        language: system
        pass_filenames: false
        always_run: true
```

3. Install the pre-commit hooks:
```bash
pre-commit install
```

## Manual Execution

If you prefer to run these commands manually before each push, you can use this combined command:

```bash
# Format and lint code
black . --exclude="/(venv|build|dist)/" && \
isort . --profile black --skip venv --skip build --skip dist && \
flake8 . --exclude=venv,build,dist --max-line-length=88 --extend-ignore=E203,W503 && \
bandit -r . -f json -o bandit-report.json --exclude ./venv,./build,./dist && \
python -m pytest tests/ -v --tb=short && \
echo "All pre-commit checks passed!"
```

## Fixing Common Issues

### Black Formatting Issues
If black reports formatting issues, run:
```bash
black . --exclude="/(venv|build|dist)/"
```

### Import Sorting Issues
If isort reports import sorting issues, run:
```bash
isort . --profile black --skip venv --skip build --skip dist
```

### Security Issues
Review the `bandit-report.json` file for security issues and fix them by:
- Adding `# nosec` comments for false positives
- Fixing actual security vulnerabilities
- Using secure alternatives for flagged functions

### Test Failures
Fix failing tests by:
- Updating test expectations
- Fixing bugs in the implementation
- Adding missing test dependencies

## CI/CD Integration

These commands are also integrated into the GitHub Actions workflows:
- `ci.yml` - Runs formatting checks, linting, and tests
- `benchmark.yml` - Runs performance benchmarks
- `release.yml` - Runs all checks before creating releases

Make sure all pre-commit checks pass locally before pushing to avoid CI/CD failures.