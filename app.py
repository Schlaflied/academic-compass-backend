# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# “学术罗盘”后端核心应用 (Academic Compass Backend Core)
# 版本: 3.0 - Project Lens 同步升级版
# 描述: 集成了基于IP的每日请求限流功能，并重构了AI分析逻辑，
#       使其能够生成带有引用来源的报告，风格与Project Lens保持一致。
# -----------------------------------------------------------------------------

import os
import requests
import google.generativeai as genai
import time
import re
from flask import Flask, request, jsonify
from flask_cors import CORS
# --- 新增：导入限流库 ---
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# --- 1. 初始化和配置 ---
app = Flask(__name__)
CORS(app)

# --- 新增：初始化限流器 ---
# 使用 get_remote_address 来根据用户的IP地址进行限流
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"], # 设置默认的全局限流
    storage_uri="memory://" # 使用内存存储
)

# --- 2. API密钥配置 (无变化) ---
try:
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    SEARCH_API_KEY = os.getenv("SEARCH_API_KEY")
    SEARCH_ENGINE_ID = os.getenv("SEARCH_ENGINE_ID")
    if not all([GEMINI_API_KEY, SEARCH_API_KEY, SEARCH_ENGINE_ID]):
        raise ValueError("一个或多个API密钥/环境变量缺失。")
    genai.configure(api_key=GEMINI_API_KEY)
    print("✅ 所有API密钥配置成功！")
except Exception as e:
    print(f"❌ API密钥配置失败: {e}")

# --- 3. 辅助函数：执行Google搜索 (有小幅修改) ---
def perform_google_search(query, api_key, cse_id, num_results=3):
    url = "https://www.googleapis.com/customsearch/v1"
    params = {'key': api_key, 'cx': cse_id, 'q': query, 'num': num_results}
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        search_results = response.json()
        # 【修改】现在同时返回摘要(snippet)和完整的来源信息(items)
        items = search_results.get('items', [])
        snippets = [item.get('snippet', '') for item in items]
        sources = [{'title': item.get('title'), 'link': item.get('link')} for item in items]
        return snippets, sources
    except requests.exceptions.RequestException as e:
        print(f"Google搜索请求失败: {e}")
        return [], []

# --- 4. 核心AI指令 (Prompt) (完全重写) ---
PROMPT_TEMPLATE = """
As 'Academic Compass', a top-tier career planning AI mentor, your task is to generate a detailed analysis report based on the provided information.
**Crucially, you must adhere to the citation rules and generate the entire response strictly in {output_language}.**

**Citation Rules (VERY IMPORTANT):**
1.  The research data provided below is structured with a unique `[Source ID: X]`.
2.  When you use information from a source, you **MUST** append its corresponding ID tag at the end of the sentence.
3.  **DO NOT GROUP CITATIONS.** Each citation must be in its own brackets. For example, to cite sources 1 and 2, you MUST write it as `[Source ID: 1][Source ID: 2]`. **NEVER write `[Source ID: 1, 2]`**.
4.  At the end of your entire report, you **MUST** include a section titled `---REFERENCES---`.
5.  Under this title, list **ONLY** the sources you actually cited. Format it as: `[Source ID: X] Title of the source`.

**Information Provided:**
1.  **User's Profile:**
    - **Major/Field of Study:** {major}
    - **Interests/Skills:** {interests}
2.  **User's Resume/Bio (if provided):**
    ```
    {resume_text}
    ```
3.  **Research Data (Search results from job sites, academic papers, articles, etc.):**
    ```
    {context_with_sources}
    ```

**Your Task:**
Synthesize all the information to create an inspiring and actionable analysis report with citations. The report MUST include the following sections IN THIS ORDER:

**1. Potential Career Path Analysis:**
Identify and describe 2-3 distinct career paths (e.g., "The Industry Researcher," "The Startup Founder," "The Academic Scholar"). For each path, analyze its core responsibilities, required skills, and industry outlook. **Cite your sources for every claim.**

**2. Salary & Job Market Insights (Canada-focused):**
Based on the research data, provide salary expectations and job market trends for the identified paths, with a focus on the Canadian market if information is available. **Cite your sources.**

**3. Personalized Match & Development Plan (if resume is provided):**
Analyze how well the applicant's background (from the resume) matches the identified career paths. Provide a brief match report and suggest 2-3 concrete steps for skill development or resume optimization. **Cite your sources.** If no resume is provided, state that this section is unavailable.

**4. Final Recommendations:**
Conclude with a summary and provide a final recommendation on which path might be the most promising, justifying your reasoning with evidence from ALL previous sections. **Cite the sources** that led to your conclusion.

**Remember to end your response with the `---REFERENCES---` section.**
"""
# --- End of Prompt ---

# --- 5. API路由 (完全重构) ---
@app.route('/analyze', methods=['POST'])
@limiter.limit("5 per day") # --- 新增：应用限流规则！每天每个IP 5次 ---
def analyze_academic_profile():
    print("--- 🧭 Academic Compass v3.0 Analysis Request Received! ---")
    try:
        data = request.get_json()
        major = data.get('major')
        interests = data.get('interests', '')
        resume_text = data.get('resumeText', 'No resume provided.')
        lang_code = data.get('language', 'en')

        if not major:
            return jsonify({"error": "专业/研究领域是必填项。"}), 400

        # 【重构】引入source_map和context_blocks来管理引用源
        context_blocks = []
        source_map = {}
        source_id_counter = 1

        print(f"🔍 Searching for: {major} in Canada...")
        
        # 加拿大本地化搜索查询
        primary_query_subject = f'"{major}"'
        if interests:
            primary_query_subject += f' AND "{interests}"'
        location_keyword = "Canada"

        search_queries = [
            f'{primary_query_subject} career paths {location_keyword}',
            f'{primary_query_subject} salary {location_keyword} site:glassdoor.ca OR site:ca.indeed.com/salaries',
            f'{primary_query_subject} jobs {location_keyword} site:ca.indeed.com OR site:linkedin.com/jobs',
            f'{primary_query_subject} skills required {location_keyword}'
        ]
        
        # 【重构】处理搜索结果，并为每个来源分配ID和类型
        for query in search_queries:
            snippets, sources_data = perform_google_search(query, SEARCH_API_KEY, SEARCH_ENGINE_ID, num_results=2)
            for i, snippet in enumerate(snippets):
                if i < len(sources_data):
                    source_info = sources_data[i]
                    link = source_info.get('link', '').lower()
                    
                    # 判断来源类型
                    if 'linkedin.com' in link:
                        source_info['source_type'] = 'linkedin'
                    elif 'glassdoor.com' in link or 'glassdoor.ca' in link:
                        source_info['source_type'] = 'glassdoor'
                    elif 'indeed.com' in link or 'ca.indeed.com' in link:
                        source_info['source_type'] = 'indeed'
                    else:
                        source_info['source_type'] = 'default'

                    context_blocks.append(f"[Source ID: {source_id_counter}] {snippet}")
                    source_map[source_id_counter] = source_info
                    source_id_counter += 1
            time.sleep(0.5) # 避免请求过于频繁
        
        if not context_blocks:
             return jsonify({"analysis": "No information found for this major.", "sources": []})

        context_with_sources = "\n\n".join(context_blocks)
        print(f"  -> Prepared {len(context_blocks)} context blocks for AI.")

        language_instructions = {'en': 'English', 'zh-CN': 'Simplified Chinese (简体中文)', 'zh-TW': 'Traditional Chinese (繁體中文)'}
        output_language = language_instructions.get(lang_code, 'English')

        full_prompt = PROMPT_TEMPLATE.format(
            output_language=output_language,
            major=major,
            interests=interests or "Not provided",
            resume_text=resume_text,
            context_with_sources=context_with_sources
        )

        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        response = model.generate_content(full_prompt)
        ai_response_text = response.text
        
        print("  -> Received response from Gemini. Parsing citations...")

        # 【重构】解析AI回复，分离报告和引用
        analysis_part = ai_response_text
        final_sources = []

        if "---REFERENCES---" in ai_response_text:
            parts = ai_response_text.split("---REFERENCES---")
            analysis_part = parts[0].strip()
            references_part = parts[1].strip()
            
            # 从 ---REFERENCES--- 部分提取被引用的ID
            cited_ids = re.findall(r'\[Source ID: (\d+)\]', references_part)
            
            for sid_str in cited_ids:
                sid = int(sid_str)
                if sid in source_map:
                    source_detail = source_map[sid]
                    source_detail['id'] = sid
                    final_sources.append(source_detail)
            
            # 将正文中的 [Source ID: X] 替换为更简洁的 [X]
            analysis_part = re.sub(r'\[Source ID: (\d+)\]', r'[\1]', analysis_part)

        print(f"  -> Successfully parsed {len(final_sources)} cited sources.")
        return jsonify({"analysis": analysis_part, "sources": final_sources})

    except Exception as e:
        print(f"!!! 发生未知错误: {e} !!!")
        return jsonify({"error": "An internal server error occurred."}), 500

# --- 新增：自定义限流错误处理函数 ---
@app.errorhandler(429)
def ratelimit_handler(e):
    # 这是为你定制的提示信息
    error_message = (
        "同学，您今日的免费探索次数已用尽！🧭\n\n"
        "Academic Compass 每天为所有用户提供5次免费生涯规划分析。\n"
        "如果需要更多支持，欢迎明天再来探索，或通过‘请我喝杯咖啡☕️’来支持项目发展！"
    )
    # 返回一个特殊的字段，让前端可以识别这是限流错误
    return jsonify(error="rate_limit_exceeded", message=error_message), 429


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port, debug=True)



