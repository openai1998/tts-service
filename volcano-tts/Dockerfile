FROM python:3.9-slim

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install -r requirements.txt && \
    # 确保python-dotenv被安装，用于加载.env文件
    pip install python-dotenv --no-cache-dir

# 创建日志目录
RUN mkdir -p /app/logs && chmod 777 /app/logs

# 复制应用代码
COPY . .

# 暴露端口
EXPOSE 5050

# 设置卷挂载点
VOLUME ["/app/logs"]

# 启动应用
CMD ["python", "app.py"]
