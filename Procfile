web: gunicorn main:web_app --log-file -
worker: python main.py --run-bot
```*(I have added `--log-file -` to the web process to ensure its logs are also correctly streamed, a standard best practice.)*

**File 2: `requirements.txt`**

This file lists all the Python libraries your project needs. The platform uses it during the "Build" phase. If `gunicorn` is not in this file, the `web` process will fail to start. Its content must be:
