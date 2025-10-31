# Setup and Environment Guide

## Virtual Environment Setup

The project uses a Python virtual environment to manage dependencies. The venv is already set up at `venv/`.

### Why Virtual Environment?

- Keeps project dependencies isolated from system Python
- Ensures consistent package versions
- Avoids conflicts with other Python projects

### Running the Scraper

**You MUST use the virtual environment.** Here are your options:

#### Option 1: Use the Helper Script (Easiest)
```bash
./run_scraper.sh
```

#### Option 2: Activate venv Manually
```bash
source venv/bin/activate
python scraper.py
```

#### Option 3: Use venv Python Directly
```bash
venv/bin/python scraper.py
```

### Common Error

If you see:
```
ModuleNotFoundError: No module named 'requests'
```

This means you're running Python outside the virtual environment. Use one of the methods above.

## About __pycache__

`__pycache__` directories contain compiled Python bytecode (`.pyc` files). These are automatically created when Python runs `.py` files.

### Are they a problem?

- **Root `__pycache__`**: Can be safely deleted (it's in `.gitignore`)
- **`venv/__pycache__`**: Normal part of the virtual environment, leave it alone
- **Purpose**: Speeds up Python imports (pre-compiled code)

### Cleaning up

If you want to clean up cache files:
```bash
# Remove root-level cache only
rm -rf __pycache__

# Or find all caches (be careful - some are in venv)
find . -type d -name __pycache__ -not -path "./venv/*" -exec rm -rf {} +
```

They're already in `.gitignore` so they won't be committed to git.

## Reinstalling Dependencies

If you need to recreate the virtual environment:

```bash
# Remove old venv
rm -rf venv

# Create new venv
python3 -m venv venv

# Activate it
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Verifying Setup

Check if everything is set up correctly:

```bash
# Check venv exists
ls venv/bin/python*

# Check dependencies are installed
venv/bin/python -c "import requests, bs4; print('✓ Dependencies OK')"

# Test run (will show help or start scraping)
venv/bin/python scraper.py
```

