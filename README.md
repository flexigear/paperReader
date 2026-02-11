# paper reader

AI 论文阅读器（Web 版）原型项目。

## 已实现功能

- 上传 PDF 论文（PC/Android/iPhone 浏览器均可）。
- 服务端接收论文并异步解析文本。
- 调用模型生成中/英/日三语总结：
  - 问题是什么（What is the question?）
  - 解决方法（What is the solution?）
  - 发现了什么（What are the findings?）
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

- 深度总结模型：`gpt-4.1`
- 对话模型：`gpt-4.1-mini`

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

## 目录结构

- `backend/app/main.py`: API 入口与静态页面托管
- `backend/app/services.py`: PDF 提取、分块检索、摘要生成、问答逻辑
- `backend/app/db.py`: SQLite 初始化与访问
- `frontend/index.html`: 三选项卡 UI
- `frontend/app.js`: 前端交互逻辑
- `frontend/styles.css`: 样式
- `data/uploads/`: 论文文件存储目录

## 当前限制

- 暂未做用户鉴权，默认单用户本地使用。
- 当前检索为词法打分（后续可升级为向量检索）。
- 自动融合依赖模型输出质量，复杂争议点仍建议手动复核。
