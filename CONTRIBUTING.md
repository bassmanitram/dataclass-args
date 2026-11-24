# Contributing to Dataclass CLI

Thank you for your interest in contributing to Dataclass CLI! This document provides guidelines and information for contributors.

## Code of Conduct

This project adheres to a standard code of conduct. By participating, you are expected to uphold respectful, inclusive, and constructive communication.

## Getting Started

### Development Setup

1. **Fork and clone the repository:**
   ```bash
   git clone https://github.com/your-username/dataclass-args.git
   cd dataclass-args
   ```

2. **Create a virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install development dependencies:**
   ```bash
   pip install -e ".[dev,all]"
   ```

4. **Verify installation:**
   ```bash
   python -c "from dataclass_args import build_config; print('✅ Installation successful!')"
   ```

### Development Workflow

1. **Create a feature branch:**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes** following the guidelines below

3. **Run tests:**
   ```bash
   pytest
   pytest --cov=dataclass_args  # With coverage
   ```

4. **Format code:**
   ```bash
   black dataclass_args/ tests/ examples/
   isort dataclass_args/ tests/ examples/
   ```

5. **Type checking:**
   ```bash
   mypy dataclass_args/
   ```

6. **Commit and push:**
   ```bash
   git add .
   git commit -m "feat: add your feature description"
   git push origin feature/your-feature-name
   ```

7. **Create a pull request**

## Contribution Guidelines

### Code Style

- **Python Version**: Support all non-EOL Python versions (currently 3.11+; tested on 3.11–3.14)
- **Formatting**: Use Black with line length 88
- **Import Sorting**: Use isort with Black profile
- **Type Hints**: Use type hints for all public APIs
- **Docstrings**: Use Google-style docstrings

### Code Structure

```
dataclass_args/
├── __init__.py          # Main exports
├── annotations.py       # Field annotations
├── builder.py          # Core GenericConfigBuilder
├── exceptions.py       # Custom exceptions
├── file_loading.py     # File loading utilities
└── utils.py           # Helper functions
```

### Testing

- **Coverage**: Maintain >90% test coverage
- **Test Structure**: Use pytest with clear test names
- **Test Categories**: Unit tests for all modules
- **Edge Cases**: Test error conditions and edge cases

#### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=dataclass_args --cov-report=html

# Run specific test files
pytest tests/test_basic.py
pytest tests/test_file_loading.py

# Run tests matching pattern
pytest -k "test_file_loading"
```

### Documentation

- **README**: Keep README.md up to date with new features
- **Docstrings**: Document all public functions and classes
- **Examples**: Add examples for new features
- **Type Hints**: Include type hints in documentation

## Types of Contributions

### Bug Reports

When filing bug reports, please include:

1. **Clear description** of the issue
2. **Minimal reproduction case**
3. **Expected vs actual behavior**
4. **Environment information** (Python version, OS, etc.)
5. **Error messages** and stack traces

**Template:**
```markdown
## Bug Description
Brief description of the issue

## Reproduction Steps
1. Step 1
2. Step 2
3. Step 3

## Expected Behavior
What should happen

## Actual Behavior
What actually happens

## Environment
- Python version: 3.x.x
- dataclass-args version: x.x.x
- OS: Linux/Windows/macOS
```

### Feature Requests

For feature requests, please include:

1. **Use case description**
2. **Proposed API design**
3. **Examples** of how it would be used
4. **Backward compatibility** considerations

### Pull Requests

#### Before Submitting

- [ ] Tests pass locally
- [ ] Code is formatted (Black + isort)
- [ ] Type checking passes (mypy)
- [ ] Documentation updated if needed
- [ ] CHANGELOG.md updated for significant changes

#### PR Description Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Tests added/updated
- [ ] All tests pass
- [ ] Manual testing completed

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] No breaking changes (or clearly documented)
```

## Development Areas

### Core Features

- **Builder enhancements**: New field types, validation rules
- **File loading**: Additional formats, preprocessing
- **Type support**: Better handling of complex types
- **Performance**: Optimization opportunities

### Integrations

- **Framework integrations**: FastAPI, Django, Flask plugins
- **IDE support**: Language server, completion providers
- **CI/CD**: GitHub Actions, pre-commit hooks

### Documentation

- **Tutorials**: Step-by-step guides for common use cases
- **API Reference**: Comprehensive API documentation
- **Examples**: Real-world usage examples
- **Migration guides**: Upgrade paths and compatibility

## Release Process

### Version Numbering

We follow [Semantic Versioning](https://semver.org/):

- **MAJOR**: Incompatible API changes
- **MINOR**: New functionality (backward compatible)
- **PATCH**: Bug fixes (backward compatible)

### Release Checklist

1. Update version in `pyproject.toml`
2. Update `CHANGELOG.md`
3. Run full test suite
4. Update documentation
5. Create release PR
6. Tag release after merge
7. Publish to PyPI

## Getting Help

### Communication Channels

- **GitHub Issues**: Bug reports and feature requests
- **GitHub Discussions**: Questions and community discussion
- **Pull Requests**: Code review and collaboration

### Areas for Help

- **Testing**: Edge cases, platform-specific testing
- **Documentation**: Examples, tutorials, API docs
- **Performance**: Profiling, optimization
- **Integrations**: Framework plugins, tooling

## Recognition

Contributors will be:

- Listed in the repository contributors
- Mentioned in release notes for significant contributions
- Added to a contributors file (if created)

## License

By contributing, you agree that your contributions will be licensed under the same MIT License that covers the project.

---

Thank you for contributing to Dataclass CLI! 🎉
