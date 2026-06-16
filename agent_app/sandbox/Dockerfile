FROM python:3.11-slim

RUN pip install --no-cache-dir numpy scipy matplotlib pandas scikit-learn sympy \
    && useradd -m -s /bin/bash sandbox

WORKDIR /workspace

# code.py 在运行时通过 docker cp 或 volume mount 注入
USER sandbox
CMD ["python", "/workspace/code.py"]
