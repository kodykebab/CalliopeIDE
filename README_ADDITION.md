
## Testing & CI/CD

[![CI Pipeline](https://github.com/kentuckyfriedcode/CalliopeIDE/actions/workflows/ci.yml/badge.svg)](https://github.com/kentuckyfriedcode/CalliopeIDE/actions/workflows/ci.yml)
[![Linting](https://github.com/kentuckyfriedcode/CalliopeIDE/actions/workflows/lint.yml/badge.svg)](https://github.com/kentuckyfriedcode/CalliopeIDE/actions/workflows/lint.yml)

Calliope IDE includes comprehensive testing infrastructure:

- **29 automated tests** (17 frontend + 12 backend)
- **GitHub Actions CI/CD** for automated testing
- **Code quality checks** with ESLint

### Running Tests

**Frontend:**
```bash
npm test
```

**Backend:**
```bash
cd server && python3 -m pytest -v
```

See [TESTING.md](TESTING.md) for detailed testing documentation.
