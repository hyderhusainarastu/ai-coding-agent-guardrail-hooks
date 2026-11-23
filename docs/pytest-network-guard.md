# Keep tests from calling paid APIs

An agent that runs your test suite can trigger real network calls, including calls to paid LLM APIs. Use the existing `pytest-socket` plugin; this repo ships no plugin code.

```sh
pip install pytest-socket
python -m pytest --disable-socket --allow-hosts=127.0.0.1
```

`--disable-socket` makes any socket creation fail the test, and `--allow-hosts` lets listed hosts through (here, loopback for local fixtures). Put the flags in `pyproject.toml` so agents get them without being told:

```toml
[tool.pytest.ini_options]
addopts = "--disable-socket --allow-hosts=127.0.0.1"
```

Add an environment check in `conftest.py` so a test run that has real API keys exported fails loudly instead of silently relying on the socket block:

```python
import os
import pytest

API_KEY_VARS = ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY")  # extend for your providers


def pytest_sessionstart(session):
    present = [name for name in API_KEY_VARS if os.environ.get(name)]
    if present:
        pytest.exit("API key variables are set: " + ", ".join(present) + ". Unset them to run tests.", returncode=2)
```

Limits: this stops Python tests that use sockets in the test process. Subprocesses that load their own plugins, native code that opens sockets before the plugin loads, and any test marked to enable sockets are not covered. Use a container with no network for a hard guarantee.
