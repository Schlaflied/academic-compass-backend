# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# “学术罗盘”后端核心应用 (Academic Compass Backend Core)
# 版本: 1.3 - 安全加固版
# 描述: 移除了硬编码的API密钥，强制使用环境变量，修复了安全漏洞。
# -----------------------------------------------------------------------------

import os
import requests
import google.generativeai as genai
from flask import Flask, request, jsonify
from flask_cors import CORS
# python-dotenv 可以在本地开发时自动从 .env 文件加载环境变量
from dotenv import load_dotenv

# --- 1. 初始化和配置 (Initialization and Configuration) ---
load_dotenv() # 加载 .env 文件中的环境变量
app = Flask(__name__)
# 允许所有来源的跨域请求，方便前后端分离开发
CORS(app)

# --- 2. API密钥配置 (API Key Configuration) ---
# 【安全更新】代码已移除所有硬编码的API密钥。
# 现在程序将严格从环境变量中读取密钥。
# 本地开发时，请在项目根目录创建 .env 文件来管理密钥。
# 部署到云端时，请在云服务提供商的控制台中设置环境变量。
try:
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    SEARCH_API_KEY = os.getenv("SEARCH_API_KEY")
    SEARCH_ENGINE_ID = os.getenv("SEARCH_ENGINE_ID")
    
    if not all([GEMINI_API_KEY, SEARCH_API_KEY, SEARCH_ENGINE_ID]):
        raise ValueError(
            "一个或多个关键的环境变量缺失 (GEMINI_API_KEY, SEARCH_API_KEY, SEARCH_ENGINE_ID)。"
            "请检查你的 .env 文件或云端配置。"
        )
    
    genai.configure(api_key=GEMINI_API_KEY)
    print("✅ 所有API密钥配置成功！(All API keys configured successfully!)")
except ValueError as e:
    print(f"❌ 配置错误 (Configuration Error): {e}")
    # 如果密钥缺失，程序将无法正常工作。
    # 在实际部署中，这应该导致服务启动失败。


# --- 3. 辅助函数 (Helper Functions) ---

def perform_google_search(query, api_key, cse_id):
    """
    执行Google自定义搜索并返回结果摘要和来源链接。
    Executes a Google Custom Search and returns snippets and sources.
    """
    url = "https://www.googleapis.com/customsearch/v1"
    params = {'key': api_key, 'cx': cse_id, 'q': query, 'num': 3}
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        search_results = response.json()
        items = search_results.get('items', [])
        snippets = [item.get('snippet', '') for item in items]
        sources = [{'title': item.get('title'), 'link': item.get('link')} for item in items]
        return snippets, sources
    except requests.exceptions.RequestException as e:
        print(f"Google搜索请求失败 (Google Search request failed): {e}")
        return [], []

def generate_search_queries(major, interests):
    """
    根据用户的专业和兴趣，动态生成一系列精确的Google搜索查询。
    Dynamically generates a series of precise Google search queries based on the user's major and interests.
    """
    primary_query_subject = f'"{major}"'
    if interests:
        primary_query_subject += f' AND "{interests}"'

    queries = [
        f'{primary_query_subject} "Research Scientist" OR "Product Manager" OR "Data Scientist" site:linkedin.com',
        f'{primary_query_subject} salary site:glassdoor.com OR site:levels.fyi',
        f'{primary_query_subject} jobs site:careers.google.com OR site:jobs.apple.com OR site:careers.microsoft.com',
        f'({primary_query_subject}) founder OR startup site:techcrunch.com OR site:ycombinator.com'
    ]
    return queries

# --- 4. 核心AI指令 (Core AI Prompt) ---
PROMPT_TEMPLATE = """
As 'Academic Compass', you are a top-tier career planning mentor. Your mission is to analyze the provided academic background and web search results to map out potential career paths for the user.
**Crucially, you must generate the entire response strictly in {output_language}.**

**Information Provided:**
1.  **Major/Field of Study:** {major}
2.  **Research Interests/Skills (if provided):** {interests}
3.  **Web Search Snippets:** The following are search results for potential careers, salaries, and jobs related to the major.
    ```
    {search_context}
    ```
4.  **Applicant's Resume/Bio (if provided):**
    ```
    {resume_text}
    ```

**Your Task:**
Synthesize all the information to create an inspiring and actionable analysis report. The report MUST be structured with the following "Career Path Cards". Generate 2-3 distinct cards.

---
### **Card 1: [Give this path a creative and fitting title, e.g., "The Research Scientist" or "The Product Visionary"]**

**1. Introduction:**
Briefly describe this career role, its core responsibilities, and its value in the industry.

**2. Evidence from the Field:**
Based on the search snippets, list 1-2 real-world examples. This could be a LinkedIn profile summary, a mention in an article, etc.
* Example: "John S., currently a Research Scientist at Google AI, focusing on quantum computing."

**3. Salary Insights:**
Provide a salary range based on the search results.
* Example: "According to Glassdoor data, the average annual salary for this role in North America is approximately $150,000 - $220,000 USD."

**4. Related Job Postings:**
List 1-2 relevant job titles or links found in the search results.
* Example: "Apple - AR/VR Human Factors Researcher"

---
### **Card 2: [Another creative and fitting title for a different path]**
...(Follow the same structure as Card 1)...
---

**(Optional) Personalized Match Analysis:**
**If and only if a resume is provided**, analyze how well the applicant's background and skills (from the resume) match the identified career paths. Provide a brief match report and 2-3 core optimization suggestions for their resume to better align with these paths. If no resume is provided, simply state: "Provide a resume for personalized analysis."
"""


# --- 5. API路由 (API Route) ---
@app.route('/analyze', methods=['POST'])
def analyze_academic_profile():
    print("--- 🧭 学术罗盘 v1.3 分析请求已收到! (Academic Compass v1.3 analysis request received!) ---")
    try:
        # 检查API密钥是否已成功加载，如果未加载则提前返回错误
        if not all([GEMINI_API_KEY, SEARCH_API_KEY, SEARCH_ENGINE_ID]):
             return jsonify({"error": "服务器API密钥未配置，请联系管理员。(Server API keys not configured. Please contact administrator.)"}), 500

        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON payload."}), 400

        major = data.get('major')
        interests = data.get('interests', '')
        resume_text = data.get('resumeText', 'No resume provided.')
        lang_code = data.get('language', 'en')

        if not major:
            return jsonify({"error": "专业/研究领域是必填项 (Major/Field of Study is required)."}), 400

        print(f"🔍 开始分析专业 (Analyzing major): {major} | 兴趣 (Interests): {interests or 'N/A'}")

        search_queries = generate_search_queries(major, interests)
        print(f"  -> 生成了 {len(search_queries)} 条搜索指令 (Generated {len(search_queries)} search queries).")

        all_snippets = []
        all_sources = []
        for query in search_queries:
            snippets, sources = perform_google_search(query, SEARCH_API_KEY, SEARCH_ENGINE_ID)
            all_snippets.extend(snippets)
            all_sources.extend(sources)

        search_context = "\n".join(all_snippets) if all_snippets else "在网络搜索中未找到相关信息 (No relevant information found in web search)."
        print(f"  -> 找到了 {len(all_snippets)} 条信息摘要 (Found {len(all_snippets)} snippets).")

        language_map = {'en': 'English', 'zh-CN': 'Simplified Chinese (简体中文)', 'zh-TW': 'Traditional Chinese (繁體中文)'}
        output_language = language_map.get(lang_code, 'English')

        full_prompt = PROMPT_TEMPLATE.format(
            output_language=output_language,
            major=major,
            interests=interests or "Not provided",
            search_context=search_context,
            resume_text=resume_text
        )

        print("  -> 正在调用Gemini API进行分析... (Calling Gemini API for analysis...)")
        model = genai.GenerativeModel('models/gemini-1.5-flash-latest')
        response = model.generate_content(full_prompt)

        print("✅ 成功从Gemini API收到响应 (Successfully received response from Gemini API).")
        return jsonify({"analysis": response.text, "sources": all_sources})

    except Exception as e:
        print(f"!!! 发生意外错误 (An unexpected error occurred): {e} !!!")
        return jsonify({"error": "服务器内部发生错误 (An internal server error occurred)."}), 500

# --- 6. 启动应用 (Run Application) ---
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port, debug=True)


