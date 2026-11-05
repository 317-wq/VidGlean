import asyncio
import os
import re
import webbrowser

import httpx
import markdown
from bilibili_api import Credential, request_settings, video
from dotenv import load_dotenv
from openai import OpenAI

# 1. 加载 .env 文件里的环境变量
load_dotenv()

# 2. 核心配置区
SESSDATA = os.getenv("BILI_SESSDATA")
request_settings.set("impersonate", "chrome131")
credential = Credential(sessdata=SESSDATA)

async def extract_bv(url_or_bv):
    """从用户输入的 URL 中提取 BV 号"""
    # 正则匹配 BV 号 (B站BV号通常是 BV 开头的 10-12 位数字+字母)
    match = re.search(r'(BV[a-zA-Z0-9]+)', url_or_bv)
    if match:
        return match.group(1)
    return None

async def main():
    print("====================================")
    print("🌟 欢迎使用 VidGlean (视频吃灰拯救者) 🌟")
    print("====================================")
    
    # 获取用户输入
    user_input = input("🔗 请输入 B 站视频链接或 BV 号: ").strip()
    if not user_input:
        print("❌ 输入不能为空！")
        return
        
    bvid = await extract_bv(user_input)
    if not bvid:
        print("❌ 无法识别出 BV 号，请检查链接格式！")
        return
        
    print(f"✅ 成功识别 BV 号: {bvid}")
    v = video.Video(bvid=bvid, credential=credential)
    
    try:
        # 获取视频基础信息
        info = await v.get_info()
        title = info['title']
        print(f"📺 视频标题: {title}")
        print(f"👤 UP主: {info['owner']['name']}")
        print("====================================")
        
        print("\n📥 正在尝试获取字幕...")
        subtitle_info = await v.get_subtitle(info['cid'])
        subtitles = subtitle_info.get('subtitles', [])
        
        if not subtitles:
            print("❌ 没找到字幕（可能是视频无字幕或鉴权失败）。")
            return

        target_sub = next((sub for sub in subtitles if 'zh' in sub['lan']), subtitles[0])
        sub_url = target_sub['subtitle_url']
        
        if sub_url.startswith("//"):
            sub_url = "https:" + sub_url
            
        print(f"✅ 找到字幕：{target_sub.get('lan_doc', '未知语言')}")
        
        # 使用 httpx 下载字幕 JSON
        async with httpx.AsyncClient() as client:
            response = await client.get(sub_url)
            data = response.json()
            
            # 拼接字幕（加逗号，避免大模型看串行）
            subtitle_text = "，".join([item['content'] for item in data['body']])
            
            # ==========================================
            # 🤖 呼叫大模型总结
            # ==========================================
            print("\n🧠 正在呼叫大模型进行知识提炼...")
            
            api_key = os.getenv("SPARK_API_KEY")
            base_url = os.getenv("SPARK_BASE_URL")
            model_id = os.getenv("SPARK_CHAT_MODEL")
            
            ai_client = OpenAI(api_key=api_key, base_url=base_url)
            
            # 强化系统提示词，强制要求 MD 格式
            system_prompt = """你是一个顶级的视频知识萃取专家。用户会给你一段未经排版、没有标点的视频字幕。
请你完成以下任务：
1. 过滤掉口语化的废话（如“大家好”、“那个”等），梳理逻辑。
2. 提炼出该视频的精华内容。
3. **必须严格使用 Markdown 语法输出**，格式要求如下：

# [这里写一个提炼后的高逼格视频标题]

## 📝 一句话总结
[用一句话概括视频的核心价值]

## 💡 核心观点
1. **[观点一标题]**：[详细解释]
2. **[观点二标题]**：[详细解释]
3. **[观点三标题]**：[详细解释]
（视视频内容，观点可以多于 3 个）

## 🔍 知识金句 / 关键名词
- 如果有重要的概念、工具名、或者非常有启发的话，列在这里。"""

            ai_response = ai_client.chat.completions.create(
                model=model_id,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": subtitle_text}
                ],
                temperature=0.5
            )
            
            # 容错处理：防止推理模型返回空 content
            if ai_response.choices[0].message.content:
                summary_md = ai_response.choices[0].message.content
            else:
                summary_md = getattr(ai_response.choices[0].message, 'reasoning_content', "生成失败")
            
            # 保存为 md 格式
            safe_title = re.sub(r'[\\/:*?"<>|]', '_', title) # 过滤文件名非法字符
            md_filename = f"{safe_title}_总结.md"
            
            with open(md_filename, "w", encoding="utf-8") as f:
                # 在文档头部加上原视频信息
                f.write(f"> **原视频**: [{title}](https://www.bilibili.com/video/{bvid})\n")
                f.write(f"> **UP主**: {info['owner']['name']}\n\n---\n\n")
                f.write(summary_md)
                
            print(f"\n💾 总结已保存为 Markdown 文档: {md_filename}")
            
            # ==========================================
            # ✨ 附加功能：生成带样式的 HTML 并在浏览器打开
            # ==========================================
            # 给 MD 加上一些好看的基础 CSS 样式
            html_content = f"""
            <html>
            <head>
                <meta charset="utf-8">
                <style>
                    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; line-height: 1.6; max-width: 800px; margin: 0 auto; padding: 20px; color: #333; }}
                    h1 {{ border-bottom: 2px solid #eaecef; padding-bottom: 10px; color: #24292e; }}
                    h2 {{ border-bottom: 1px solid #eaecef; padding-bottom: 5px; color: #0366d6; margin-top: 30px; }}
                    blockquote {{ border-left: 4px solid #dfe2e5; color: #6a737d; padding-left: 16px; margin-left: 0; background-color: #f6f8fa; padding: 10px; border-radius: 4px; }}
                    strong {{ color: #d73a49; }}
                    li {{ margin-bottom: 10px; }}
                </style>
            </head>
            <body>
                {markdown.markdown(summary_md, extensions=['fenced_code', 'tables'])}
            </body>
            </html>
            """
            html_filename = f"{safe_title}_总结.html"
            with open(html_filename, "w", encoding="utf-8") as f:
                f.write(html_content)
                
            print("🌐 正在浏览器中为你打开排版精美的总结网页...")
            # 自动在默认浏览器中打开
            webbrowser.open('file://' + os.path.realpath(html_filename))
            
    except Exception as e:
        print(f"\n❌ 运行出错: {e}")

if __name__ == '__main__':
    asyncio.run(main())