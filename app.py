# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# “学术罗盘”后端核心应用 (Academic Compass Backend Core)
# 版本: 2.0 - 加拿大本地化优化版
# 描述: 优化了搜索查询逻辑，使其优先返回加拿大的职业、薪资和职位信息。
# -----------------------------------------------------------------------------

import os
import requests
import google.generativeai as genai
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

# --- 1. 初始化和配置 (Initialization and Configuration) ---
load_dotenv() 
app = Flask(__name__)
CORS(app)

# --- 2. API密钥配置 (API Key Configuration) ---
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

# --- 3. 路由 (Routes) ---

@app.route('/', methods=['GET'])
def home():
    return "<h1>🧭 学术罗盘后端服务已成功运行！(v2.0 Canada-Optimized)</h1><p>请通过 /analyze 接口进行调用。</p>", 200

@app.route('/analyze', methods=['POST'])
def analyze_academic_profile():
    print("--- 🧭 学术罗盘 v2.0 分析请求已收到! ---")
    try:
        if not all([GEMINI_API_KEY, SEARCH_API_KEY, SEARCH_ENGINE_ID]):
             return jsonify({"error": "服务器API密钥未配置，请联系管理员。"}), 500

        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON payload."}), 400

        major = data.get('major')
        interests = data.get('interests', '')
        resume_text = data.get('resumeText', 'No resume provided.')
        lang_code = data.get('language', 'en')

        if not major:
            return jsonify({"error": "专业/研究领域是必填项。"}), 400

        print(f"🔍 开始为专业 '{major}' 进行加拿大本地化分析...")

        # 使用加拿大优化版的搜索查询生成器
        search_queries = generate_search_queries_canada(major, interests)
        print(f"  -> 生成了 {len(search_queries)} 条加拿大本地化搜索指令。")

        all_snippets = []
        all_sources = []
        for query in search_queries:
            snippets, sources = perform_google_search(query, SEARCH_API_KEY, SEARCH_ENGINE_ID)
            all_snippets.extend(snippets)
            all_sources.extend(sources)

        search_context = "\n".join(all_snippets) if all_snippets else "在网络搜索中未找到相关信息。"
        print(f"  -> 找到了 {len(all_snippets)} 条信息摘要。")

        language_map = {'en': 'English', 'zh-CN': 'Simplified Chinese (简体中文)', 'zh-TW': 'Traditional Chinese (繁體中文)'}
        output_language = language_map.get(lang_code, 'English')

        full_prompt = PROMPT_TEMPLATE.format(
            output_language=output_language,
            major=major,
            interests=interests or "Not provided",
            search_context=search_context,
            resume_text=resume_text
        )

        print("  -> 正在调用Gemini API进行分析...")
        model = genai.GenerativeModel('models/gemini-1.5-flash-latest')
        response = model.generate_content(full_prompt)

        print("✅ 成功从Gemini API收到响应。")
        return jsonify({"analysis": response.text, "sources": all_sources})

    except Exception as e:
        print(f"!!! 发生意外错误: {e} !!!")
        return jsonify({"error": "服务器内部发生错误。"}), 500

# --- 4. 辅助函数 (Helper Functions) ---

def perform_google_search(query, api_key, cse_id):
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
        print(f"Google搜索请求失败: {e}")
        return [], []

# 【加拿大优化版】
def generate_search_queries_canada(major, interests):
    """
    根据用户的专业和兴趣，动态生成一系列针对加拿大的精确Google搜索查询。
    """
    primary_query_subject = f'"{major}"'
    if interests:
        primary_query_subject += f' AND "{interests}"'
    
    # 添加加拿大地域关键词，让搜索更精准
    location_keyword = "Canada OR Ontario OR Toronto"

    queries = [
        # 查询实例1 (找人): 在LinkedIn上寻找在加拿大的从业者
        f'{primary_query_subject} ("Research Scientist" OR "Product Manager" OR "Instructional Designer") {location_keyword} site:linkedin.com',
        
        # 查询实例2 (找薪资): 在加拿大的薪资网站上寻找信息
        f'{primary_query_subject} salary Canada site:glassdoor.ca OR site:ca.indeed.com/salaries',
        
        # 查询实例3 (找职位): 在加拿大的招聘网站上寻找相关职位
        f'{primary_query_subject} jobs {location_keyword} site:ca.indeed.com OR site:linkedin.com/jobs',
        
        # 查询实例4 (找创业者): 寻找加拿大的创业者故事 (BetaKit和Techvibes是加拿大顶尖的科技新闻网站)
        f'({primary_query_subject}) founder OR startup {location_keyword} site:betakit.com OR site:techvibes.com'
    ]
    return queries

# --- 5. 核心AI指令 (Core AI Prompt) ---
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

# --- 6. 启动应用 (Run Application) ---
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port, debug=False)





