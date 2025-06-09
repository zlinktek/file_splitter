# How to generate .exe

use pyinstaller to convert .py to .exe

```bash
pyinstaller --clean --target-architecture=32bit --add-data ".;." --onefile --noconsole main.py
```
