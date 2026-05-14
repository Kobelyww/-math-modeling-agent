FROM python:3.11-slim

RUN pip install --no-cache-dir numpy scipy matplotlib pandas scikit-learn sympy \
    && useradd -m -s /bin/bash sandbox

WORKDIR /workspace
COPY code.py /workspace/

USER sandbox

CMD ["python", "code.py"]
