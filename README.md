# nanoGen: Vertex 图生图/图像编辑 API

使用 `gemini-3.1-flash-image-preview` 做 Image-to-Image（上传参考图 + 文本提示词），并通过 FastAPI 暴露接口，部署到 Cloud Run。
页面支持在下拉框中切换模型（默认内置 3 个最新 image 模型）。

## 1. 项目结构

```txt
.
├── .env.example
├── main.py
├── web/index.html
├── requirements.txt
├── Dockerfile
└── .dockerignore
```

## 2. 前置条件

- 已安装并登录 `gcloud`
- GCP 项目已开通结算
- 你的账号对目标项目有部署权限

## 3. 本地运行

### 3.1 安装依赖

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3.2 配置环境变量

推荐用 `.env` 文件管理本地变量（不要提交到仓库）：

```bash
cp .env.example .env
# 编辑 .env，把 your-project-id 改成你的项目 ID
```

加载 `.env`（bash/zsh 都可）：

```bash
set -a
source .env
set +a
```

说明：

- `.env` 只用于本地开发，已通过 `.gitignore` 排除。
- 不要把密钥写进代码或提交到 Git。
- 本项目调用 Vertex AI 使用 ADC，不需要保存 API Key。
- `GEMINI_MODEL_ID` 是默认模型；`ALLOWED_IMAGE_MODELS` 是前端可选模型白名单（逗号分隔）。

### 3.3 本地鉴权（ADC）

```bash
gcloud auth application-default login
```

### 3.4 启动服务

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8080
```

打开浏览器：

```txt
http://127.0.0.1:8080/
```

你会看到可视化页面：上传图片、输入提示词、点击生成、下载结果。
新界面是左右布局：左侧原图（支持 Ctrl/Cmd+V 粘贴图片），右侧结果图，底部是 Prompt + 模型选择。

健康检查：

```bash
curl http://127.0.0.1:8080/healthz
```

图像编辑测试：

```bash
curl -X POST "http://127.0.0.1:8080/edit" \
  -F "prompt=把这张图改成赛博朋克夜景，保留主体构图" \
  -F "model=gemini-3.1-flash-image-preview" \
  -F "image=@input.jpg" \
  --output output.png
```

## 4. 部署到 Cloud Run

### 4.1 启用 API

```bash
gcloud services enable \
  aiplatform.googleapis.com \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com
```

### 4.2 创建运行时服务账号并授权

```bash
gcloud iam service-accounts create vertex-img-sa

gcloud projects add-iam-policy-binding "$GOOGLE_CLOUD_PROJECT" \
  --member="serviceAccount:vertex-img-sa@$GOOGLE_CLOUD_PROJECT.iam.gserviceaccount.com" \
  --role="roles/aiplatform.user"
```

### 4.3 部署

```bash
gcloud run deploy img-edit-api \
  --source . \
  --region us-central1 \
  --service-account "vertex-img-sa@$GOOGLE_CLOUD_PROJECT.iam.gserviceaccount.com" \
  --allow-unauthenticated \
  --set-env-vars "^##^GOOGLE_CLOUD_PROJECT=$GOOGLE_CLOUD_PROJECT##GOOGLE_CLOUD_LOCATION=global##GEMINI_MODEL_ID=gemini-3.1-flash-image-preview##ALLOWED_IMAGE_MODELS=gemini-3.1-flash-image-preview,gemini-3-pro-image-preview,gemini-2.5-flash-image"
```

部署成功后拿到 `SERVICE_URL`，调用：

```bash
curl -X POST "$SERVICE_URL/edit" \
  -F "prompt=把画面改为电影感黄昏，提升细节" \
  -F "model=gemini-3.1-flash-image-preview" \
  -F "image=@input.jpg" \
  --output output.png
```

### 4.4 线上环境变量安全实践（Best Practice）

- 非敏感配置（如 `GOOGLE_CLOUD_LOCATION`、`GEMINI_MODEL_ID`）用 `--set-env-vars`。
- 敏感信息（数据库密码、第三方 token）放 `Secret Manager`，不要写 `.env` 上传线上。
- Cloud Run 优先使用服务账号权限，不要下载长期 JSON Key 到本地或镜像。

Secret Manager 示例：

```bash
echo -n "your-secret-value" | gcloud secrets create APP_SECRET --data-file=-

gcloud run deploy img-edit-api \
  --source . \
  --region us-central1 \
  --service-account "vertex-img-sa@$GOOGLE_CLOUD_PROJECT.iam.gserviceaccount.com" \
  --set-secrets "APP_SECRET=APP_SECRET:latest" \
  --set-env-vars "^##^GOOGLE_CLOUD_PROJECT=$GOOGLE_CLOUD_PROJECT##GOOGLE_CLOUD_LOCATION=global##GEMINI_MODEL_ID=gemini-3.1-flash-image-preview##ALLOWED_IMAGE_MODELS=gemini-3.1-flash-image-preview,gemini-3-pro-image-preview,gemini-2.5-flash-image"
```

## 5. Python 还是 Colab？

- 正式项目：`Python + Cloud Run` 最方便（稳定、可部署、可接前端/后端）。
- 原型调参：`Google Colab` 方便快速试 prompt，但不建议作为线上接口。
