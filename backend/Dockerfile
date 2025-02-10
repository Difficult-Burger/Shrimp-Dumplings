FROM swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/python:3.9-slim

# 安装系统依赖（新增 gevent 所需）
RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /app

# 将依赖文件复制到工作目录
COPY requirements.txt ./

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 将所有代码复制到工作目录
COPY . .

# 设置环境变量（微信云托管会注入 PORT 变量）
ENV PORT=5000

# 暴露端口
EXPOSE 80

# 新增 gevent 启动方式
CMD ["gunicorn", "--worker-class=geventwebsocket.gunicorn.workers.GeventWebSocketWorker", "-b", "0.0.0.0:5000", "app:app"]
