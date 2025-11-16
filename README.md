# 🧭 学术罗盘 (Academic Compass) - 后端 / Backend

这是一个专为学术和研究领域设计的 AI 职业规划后端服务。它基于用户的专业、兴趣和简历信息，自动生成包含职业路径分析、薪酬洞察和发展计划的详细报告。

This is an AI career planning backend service specifically designed for academic and research fields. It automatically generates detailed reports including career path analysis, salary insights, and development plans based on the user's major, interests, and resume.

## 核心功能 / Core Features

* **学术职业分析 / Academic Career Analysis:** 使用 **Google Gemini 1.5 Flash** 模型，根据用户的专业/学位（Major）生成 2-3 条潜在职业路径分析报告。/ Generates an analysis report featuring 2-3 potential career paths based on the user's major/degree using the **Google Gemini 1.5 Flash** model.
* **区域聚焦 / Regional Focus:** 搜索和报告的重点关注 **加拿大 (Canada)** 市场的薪酬和就业趋势。/ The search and report focus specifically on salary and employment trends within the **Canadian (Canada)** market.
* **信息可溯源 / Citable Insights:** 报告严格遵守 RAG（检索增强生成）原则，生成的每条信息都带有清晰的引用来源。/ The report strictly adheres to RAG (Retrieval-Augmented Generation) principles, with every piece of information generated including clear source citations.
* **速率限制 / Rate Limiting:** 集成 **Flask-Limiter**，对 API 调用实行严格的每日限流（默认 5 次/天/IP），以保护资源并提供稳定的免费服务。/ Integrates **Flask-Limiter** to enforce strict daily API rate limits (default 5 times/day/IP) to protect resources and provide stable free service.
* **多语言支持 / Multilingual Support:** 支持报告生成为英文、简体中文或繁体中文。/ Supports report generation in English, Simplified Chinese, or Traditional Chinese.

## 技术栈 / Tech Stack

| 模块 / Module | 组件 / Component | 描述 / Description |
| :--- | :--- | :--- |
| **框架 / Framework** | Flask | 轻量级的 Python Web 框架。/ Lightweight Python web framework. |
| **AI 引擎 / AI Engine** | `google-generativeai` | 用于调用 Gemini 1.5 Flash 模型进行分析。/ Used to call the Gemini 1.5 Flash model for analysis. |
| **限流 / Rate Limiting** | `Flask-Limiter` | 负责基于 IP 地址的请求频率控制。/ Responsible for IP-based request frequency control. |
| **部署 / Deployment** | Docker, Gunicorn | 容器化和生产环境 Web 服务器（针对 Cloud Run 优化）。/ Containerization and production web server (optimized for Cloud Run). |
| **搜索 / Search** | `requests` | 用于调用 Google Custom Search API 进行数据检索。/ Used to call the Google Custom Search API for data retrieval. |

## 部署配置 / Deployment Configuration

项目需要以下环境变量才能正常运行。/ The project requires the following environment variables to run correctly.

| 变量名 / Variable Name | 描述 / Description |
| :--- | :--- |
| `GEMINI_API_KEY` | Google Gemini API 密钥。/ Google Gemini API Key. |
| `SEARCH_API_KEY` | Google Custom Search API 密钥。/ Google Custom Search API Key. |
| `SEARCH_ENGINE_ID` | Google Custom Search Engine ID。/ Google Custom Search Engine ID. |
| `PINECONE_API_KEY` | Pinecone 向量数据库 API 密钥。/ Pinecone Vector Database API Key. |
| `PINECONE_ENVIRONMENT` | Pinecone 环境名称。/ Pinecone Environment Name. |
| `PORT` | 服务监听端口（如 `8080`），通常由 PaaS 平台（如 Cloud Run）自动注入。/ The service listening port (e.g., `8080`), usually injected automatically by PaaS platforms (like Cloud Run). |

## API 端点 / API Endpoints

| 方法 / Method | 路径 / Path | 描述 / Description |
| :--- | :--- | :--- |
| `GET` | `/` | Health Check. 检查服务运行状态。 / Checks service health status. |
| `POST` | `/analyze` | **核心分析接口**。接受专业、兴趣和简历等信息，返回生涯规划报告。/ **Core Analysis Endpoint**. Accepts major, interests, and resume text, and returns a career planning report. |

### `POST /analyze` 请求体示例 / Request Body Example

```json
{
  "major": "PhD in Computational Chemistry",
  "interests": "Quantum Computing, Python, Data Science",
  "resumeText": "5 years of research experience...",
  "language": "zh-CN"
}
