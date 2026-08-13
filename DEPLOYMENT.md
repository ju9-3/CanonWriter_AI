# 🚀 CanonWriter 部署指南（永久在线链接）

本指南将帮助你把项目部署到云端，获得一个 24 小时在线的永久链接。

## 架构说明

```
┌─────────────────────┐     ┌──────────────────────┐
│  GitHub Pages       │────→│  Render.com          │
│  (前端 - 静态网页)  │ API │  (后端 - Python 服务) │
│  免费，永久在线     │     │  免费，永久在线       │
└─────────────────────┘     └──────────────────────┘
  https://你的用户名.github.io    https://your-app.onrender.com
```

## 准备工作

1. [ ] 注册 GitHub 账号（https://github.com）
2. [ ] 注册 Render 账号（https://render.com）
3. [ ] 安装 Git（https://git-scm.com/download/win）

---

## 第一步：部署后端到 Render

### 1.1 创建 GitHub 仓库并上传后端代码

```bash
# 进入后端目录
cd C:\Users\喵\Desktop\小说创作助手\backend\CanonWriter小说项目

# 初始化 Git
git init
git add .
git commit -m "Initial commit"

# 在 GitHub 上创建一个仓库，比如 canonwriter-backend
# 然后推送到 GitHub
git remote add origin https://github.com/ju9-3/canonwriter-backend.git
git push -u origin main
```

### 1.2 在 Render 上部署

1. 登录 https://render.com
2. 点击 **New** → **Web Service**
3. 选择你的 GitHub 仓库 `canonwriter-backend`
4. 配置服务：
   - **Name**: `canonwriter-api`
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn -w 4 -k 200 -b 0.0.0.0:$PORT -t 120 api_server:app`
5. 点击 **Advanced** → **Environment** → 添加环境变量：
   - Key: `DASHSCOPE_API_KEY`, Value: 你的 API Key
   - Key: `DASHSCOPE_BASE_URL`, Value: `https://dashscope.aliyuncs.com/compatible-mode/v1`
6. 点击 **Create Web Service**

等待部署完成（约 2-5 分钟），你会得到一个后端地址，例如：
```
https://canonwriter-api.onrender.com
```

---

## 第二步：部署前端到 GitHub Pages

### 2.1 修改前端配置

打开 `frontend/api.js`，将后端地址替换为你自己的 Render 地址：

```javascript
// 修改这一行：
: 'https://你的后端地址.onrender.com';  // 替换为实际地址
```

### 2.2 上传前端到 GitHub

```bash
# 进入前端目录
cd C:\Users\喵\Desktop\小说创作助手\frontend

# 初始化 Git
git init
git add .
git commit -m "Initial commit"

# 在 GitHub 上创建另一个仓库，比如 canonwriter-frontend
git remote add origin https://github.com/你的用户名/canonwriter-frontend.git
git push -u origin main
```

### 2.3 启用 GitHub Pages

1. 打开前端仓库页面
2. 点击 **Settings** → **Pages**
3. Source 选择 **Deploy from a branch**
4. Branch 选择 **main**，文件夹选择 **/ (root)**
5. 点击 **Save**

等待 1-2 分钟，你会得到前端地址：
```
https://你的用户名.github.io/canonwriter-frontend/
```

---

## 第三步：验证

1. 打开前端链接
2. 登录系统
3. 上传文件、测试生成功能
4. 如果功能正常，复制这个链接放到简历上即可！

## 常见问题

### Q: 免费额度够用吗？
A: Render 免费版：750 小时/月，足够个人演示。GitHub Pages 完全免费，无限制。

### Q: 云端运行慢怎么办？
A: 首次加载模型会慢一些（embedding 模型约 100MB），之后会快很多。可以考虑升级 Render 付费计划。

### Q: 能绑定自定义域名吗？
A: 可以，但需要购买域名。目前用 GitHub Pages 提供的免费域名足够简历使用。

### Q: 能支持 HTTPS 吗？
A: GitHub Pages 和 Render 都默认支持 HTTPS，无需额外配置。

---

## 快速命令参考

```bash
# 后端本地运行
cd backend/CanonWriter小说项目
.venv\Scripts\python.exe -m uvicorn api_server:app --host 0.0.0.0 --port 8000

# 前端本地运行
cd frontend
python -m http.server 3000

# 本地访问
# http://localhost:3000
```
