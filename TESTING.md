# Testing Guide

This document explains how to run and write tests for Calliope IDE.

## Running Tests

### Frontend Tests
```bash
# Run all frontend tests
npm test

# Run tests in watch mode
npm run test:watch
```

### Backend Tests
```bash
# Navigate to server directory
cd server

# Run all backend tests
python3 -m pytest -v

# Run specific test file
python3 -m pytest tests/test_api.py -v
```

### Run All Tests
```bash
# Frontend
npm test

# Backend
cd server && python3 -m pytest -v && cd ..
```

## Test Coverage

### Current Coverage
- **Frontend**: 17 tests covering components, theme, chat, and layout
- **Backend**: 12 tests covering API, agent logic, and integration flows
- **Total**: 29 comprehensive tests

### Frontend Test Structure
```
tests/
├── setup.ts                    # Jest configuration
├── components/
│   ├── basic.test.tsx         # Basic framework tests
│   ├── theme-toggle.test.tsx  # Theme switching logic
│   ├── navbar.test.tsx        # Navigation tests
│   ├── chat.test.tsx          # Chat interface tests
│   └── layout.test.tsx        # Layout responsiveness
```

### Backend Test Structure
```
server/tests/
├── __init__.py
├── test_api.py          # API endpoint tests
├── test_agent.py        # AI agent functionality
└── test_integration.py  # End-to-end flows
```

## Writing New Tests

### Frontend Test Example
```typescript
describe('Component Name', () => {
  it('should perform expected behavior', () => {
    const result = someFunction();
    expect(result).toBe(expectedValue);
  });
});
```

### Backend Test Example
```python
def test_feature_name():
    """Test description"""
    result = some_function()
    assert result == expected_value
```

## Continuous Integration

Tests run automatically on:
- Every push to `main` and `develop` branches
- Every pull request

### CI Pipeline includes:
- ✅ Frontend tests (Jest)
- ✅ Backend tests (pytest)
- ✅ Linting (ESLint)
- ✅ Build verification

Check the Actions tab on GitHub to see test results.

## Troubleshooting

### Frontend tests failing
```bash
# Clear cache and reinstall
rm -rf node_modules package-lock.json
npm install --legacy-peer-deps
npm test
```

### Backend tests failing
```bash
# Reinstall pytest
pip install pytest pytest-flask pytest-mock --break-system-packages
cd server && python3 -m pytest -v
```

## Adding Dependencies

### Frontend
```bash
npm install --save-dev package-name --legacy-peer-deps
```

### Backend
```bash
pip install package-name --break-system-packages
# Add to server/requirements-dev.txt
```
