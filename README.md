# paper reader

AI 论文阅读器（Web 版）原型项目。

## 已实现功能

- 上传 PDF 论文（PC/Android/iPhone 浏览器均可）。
- 服务端接收论文并异步解析文本。
- 调用模型生成中/英/日三语总结：
  - 本论文要解决的问题（回答式描述）
  - 如何解决该问题（回答式描述）
  - 基于上述解决方案，得到了什么结果（回答式描述）
- 三选项卡 UI：
  - `UPLOAD`：上传论文
  - `PAPER`：查看当前论文原文
  - `RESULTS`：结果列表（横向滚动）+ 详情 + AI 对话
- 已实现检索增强问答（RAG）：
  - 论文按页分块并写入 `chunks` 索引
  - 每次提问先检索相关片段，再让模型回答
  - 回答要求给出页码引用（如 `[Page 7]`）
- 已实现“讨论后更新总结”：
  - 每轮对话后自动融合到三语总结
  - 记录总结版本号与最近更新时间
- 已实现上传去重：
  - 上传时按论文内容指纹与规范化标题比对
  - 命中已处理论文时复用历史结果，不重复解析

## 技术栈

- Backend: FastAPI + SQLite
- PDF 解析: pypdf
- LLM: OpenAI Responses API
- Frontend: 原生 HTML/CSS/JS（移动端自适应）

## 模型建议

- 深度总结模型：`gpt-5.2-pro`
- 对话模型：`gpt-5.2-pro`

可通过环境变量覆盖：

- `OPENAI_SUMMARY_MODEL`
- `OPENAI_CHAT_MODEL`

## 快速启动

```bash
cd /mnt/projects/paperReader
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export OPENAI_API_KEY="<your_api_key>"
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

打开 `http://localhost:8000`。

## Debian 后台脚本

```bash
cd /mnt/projects/paperReader
scripts/paperreader-start.sh     # 后台启动
scripts/paperreader-status.sh    # 查看状态
scripts/paperreader-restart.sh   # 重启服务
scripts/paperreader-stop.sh      # 停止服务
```

说明：
- 日志文件：`.run/paper-reader.log`
- 进程文件：`.run/paper-reader.pid`
- 可通过环境变量覆盖监听地址：`HOST`、`PORT`
- 若存在 `.env`，`paperreader-start.sh` 会自动加载（可在其中放 `OPENAI_API_KEY`）

## 目录结构

- `backend/app/main.py`: API 入口与静态页面托管
- `backend/app/services.py`: PDF 提取、分块检索、摘要生成、问答逻辑
- `backend/app/db.py`: SQLite 初始化与访问
- `frontend/index.html`: 三选项卡 UI
- `frontend/app.js`: 前端交互逻辑
- `frontend/styles.css`: 样式
- `data/uploads/`: 论文文件存储目录

## 文档入口

- `docs/PROJECT_STATE.md`: 当前状态、已完成、风险与下一步
- `docs/architecture.md`: 系统架构、流程、数据模型与约束
- `docs/API.md`: 接口说明与示例
- `docs/CHANGELOG.md`: 变更历史
- `docs/WORKLOG.md`: 工作记录（便于会话续接）

## 当前限制

- 暂未做用户鉴权，默认单用户本地使用。
- 当前检索为词法打分（后续可升级为向量检索）。
- 自动融合依赖模型输出质量，复杂争议点仍建议手动复核。
