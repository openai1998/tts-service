FROM python:3.9-slim

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 创建必要的目录并设置权限
RUN mkdir -p logs DEBUG/text DEBUG/audio && \
    chmod -R 777 logs DEBUG && \
    chown -R nobody:nogroup logs DEBUG && \
    ls -la DEBUG

# 暴露端口
EXPOSE 5050

# 设置卷挂载点
VOLUME ["/app/logs", "/app/DEBUG"]

# 启动应用
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "5050", "--log-level", "debug"]
