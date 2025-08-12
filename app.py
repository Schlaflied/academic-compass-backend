# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# “学术罗盘”后端核心应用 (Academic Compass Backend Core)
# 版本: 1.2 - 配置完成，准备运行
# 描述: 根据“学术罗盘”作战蓝图V1.1构建，旨在为用户探索学术背景下的多种职业可能性。
# -----------------------------------------------------------------------------

import os
import requests
import google.generativeai as genai
from flask import Flask, request, jsonify
from flask_cors import CORS

# --- 1. 初始化和配置 (Initialization and Configuration) ---
app = Flask(__name__)
# 允许所有来源的跨域请求，方便前后端分离开发
CORS(app)

# --- 2. API密钥配置 (API Key Configuration) ---
# 优先从环境变量加载API密钥，这是云部署的最佳实践
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
SEARCH_API_KEY = os.getenv("SEARCH_API_KEY")
SEARCH_ENGINE_ID = os.getenv("SEARCH_ENGINE_ID")

# 如果环境变量中没有找到，则使用你提供的密钥作为本地测试的后备
# For security, it's highly recommended to use environment variables for deployment.
if not all([GEMINI_API_KEY, SEARCH_API_KEY, SEARCH_ENGINE_ID]):
    print("⚠️ 未在环境变量中找到所有API密钥，将使用代码中为本地测试提供的后备密钥。")
    print("⚠️ For deployment, please use environment variables instead of hardcoding keys.")
    
    # 你提供的Google API密钥
    PROVIDED_API_KEY = "AIzaSyCkOT-H7wG6pqZRYuzCxsOub0v6ptQ0GA8"
    
    GEMINI_API_KEY = PROVIDED_API_KEY
    SEARCH_API_KEY = PROVIDED_API_KEY
    # 【配置完成】已使用你提供的搜索引擎ID
    # [CONFIGURATION COMPLETE] Using your provided Search Engine ID.
    SEARCH_ENGINE_ID = "c0b2c93feb47f4629" 

try:
    # 再次检查，确保所有密钥和ID都已加载
    if not all([GEMINI_API_KEY, SEARCH_API_KEY, SEARCH_ENGINE_ID]):
         raise ValueError("API密钥和搜索引擎ID未能成功加载。请检查环境变量或代码中的后备值。")
    
    genai.configure(api_key=GEMINI_API_KEY)
    print("✅ 所有API密钥配置成功！(All API keys configured successfully!)")
except Exception as e:
    print(f"❌ API密钥配置失败 (API key configuration failed): {e}")


# --- 3. 辅助函数 (Helper Functions) ---

def perform_google_search(query, api_key, cse_id):
    """
    执行Google自定义搜索并返回结果摘要和来源链接。
    Executes a Google Custom Search and returns snippets and sources.
    """
    url = "https://www.googleapis.com/customsearch/v1"
    # 'num': 3 意味着每个查询最多返回3个结果，以保持信息聚焦
    params = {'key': api_key, 'cx': cse_id, 'q': query, 'num': 3}
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()  # 如果请求失败则抛出异常
        search_results = response.json()
        # 安全地提取条目，避免因没有'items'键而出错
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
    # 如果用户输入了更具体的兴趣，将其加入到主要专业领域中，使搜索更精确
    primary_query_subject = f'"{major}"'
    if interests:
        primary_query_subject += f' AND "{interests}"'

    # 根据作战蓝图设计的查询策略
    queries = [
        # 查询实例1 (找人): 在LinkedIn上寻找该领域的从业者
        f'{primary_query_subject} "Research Scientist" OR "Product Manager" OR "Data Scientist" site:linkedin.com',
        # 查询实例2 (找薪资): 在Glassdoor和Levels.fyi上寻找薪资信息
        f'{primary_query_subject} salary site:glassdoor.com OR site:levels.fyi',
        # 查询实例3 (找职位): 在知名科技公司的招聘网站上寻找相关职位
        f'{primary_query_subject} jobs site:careers.google.com OR site:jobs.apple.com OR site:careers.microsoft.com',
        # 查询实例4 (找创业者): 在TechCrunch和YCombinator上寻找该领域的创始人
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
    print("--- 🧭 学术罗盘 v1.2 分析请求已收到! (Academic Compass v1.2 analysis request received!) ---")
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON payload."}), 400

        # 从请求中获取数据
        major = data.get('major')
        interests = data.get('interests', '') # 可选
        resume_text = data.get('resumeText', 'No resume provided.') # 可选
        lang_code = data.get('language', 'en') # 默认为英语

        if not major:
            return jsonify({"error": "专业/研究领域是必填项 (Major/Field of Study is required)."}), 400

        print(f"🔍 开始分析专业 (Analyzing major): {major} | 兴趣 (Interests): {interests or 'N/A'}")

        # 1. 生成搜索查询
        search_queries = generate_search_queries(major, interests)
        print(f"  -> 生成了 {len(search_queries)} 条搜索指令 (Generated {len(search_queries)} search queries).")

        # 2. 执行搜索并汇总结果
        all_snippets = []
        all_sources = []
        for query in search_queries:
            snippets, sources = perform_google_search(query, SEARCH_API_KEY, SEARCH_ENGINE_ID)
            all_snippets.extend(snippets)
            all_sources.extend(sources)

        search_context = "\n".join(all_snippets) if all_snippets else "在网络搜索中未找到相关信息 (No relevant information found in web search)."
        print(f"  -> 找到了 {len(all_snippets)} 条信息摘要 (Found {len(all_snippets)} snippets).")

        # 3. 准备并发送给Gemini
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
        # 4. 返回结果
        return jsonify({"analysis": response.text, "sources": all_sources})

    except Exception as e:
        print(f"!!! 发生意外错误 (An unexpected error occurred): {e} !!!")
        # 在生产环境中，你可能希望记录更详细的错误信息
        return jsonify({"error": "服务器内部发生错误 (An internal server error occurred)."}), 500

# --- 6. 启动应用 (Run Application) ---
if __name__ == '__main__':
    # Cloud Run会通过PORT环境变量设置正确的端口
    port = int(os.environ.get("PORT", 8080))
    # debug=True仅用于本地开发，在生产中应由Gunicorn管理
    app.run(host='0.0.0.0', port=port, debug=True)

