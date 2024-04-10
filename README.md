# qaml-python

Control your iOS and Android devices with natural language

## Getting Started
Make sure you have Appium installed first.

### macOS
```bash
brew install appium
```

### all other OSes
```bash
npm i -g appium
```

### Install qaml
Now install qaml
```bash
pip install qaml
```

## Examples
### Python
```python
import qaml

q = qaml.Client(api_key=<API_KEY>)

q.execute("open safari")
q.execute("scroll up")
q.execute("tap the address bar")

# Or use an existing appium driver
q = qaml.Client(driver=appium_driver, api_key=<API_KEY>)

q.execute("type camelqa.com")
q.execute("tap go")
```

### repl
```bash
export QAML_API_KEY=<API_KEY>
```

```bash
qaml
```

This will start a repl in your shell. You can issue natural language commands to get a feel for qaml.

### One-off commands
```bash
qaml tap the send button
```

## Docs
For more details visit our [docs](https://docs.camelqa.com/introduction)

Join our community on [Discord](https://discord.gg/juNYATfJTZ) for live discussions and support!
