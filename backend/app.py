from flask import Flask, request, jsonify
import requests
from dotenv import load_dotenv
import os
from flask_cors import CORS
import time
from datetime import datetime
import traceback

# 加载环境变量
load_dotenv(override=True)  # 添加强制覆盖
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY") or os.environ.get("DEEPSEEK_API_KEY")  # 双重验证

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})  # 允许所有域名
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

# 场景提示词模板
SCENARIO_PROMPTS = {
    "restaurant": (
        "你現在扮演香港茶餐廳服務員，需要使用簡單粵語與顧客對話。"
        "對話需包含：招呼用語、餐點推薦、特殊要求處理、結帳流程。"
        "請使用香港地道用詞如「唔該」、「靚仔/靚女」、「走冰」等。"
        "保持對話自然，每次回复1-2句話。"
    ),
    "street": (
        "你現在扮演熱心香港市民，需要用簡單粵語為遊客指路。"
        "對話需包含：確認目的地、描述路線（使用香港地標）、提醒注意事項。"
        "使用香港街道名稱如「彌敦道」、「砵蘭街」等。"
        "保持友好耐心，每次回复1-2句話。"
    )
}

def build_conversation_history(history):
    """将聊天历史转换为DeepSeek需要的格式"""
    return [
        {
            "role": "user" if msg["type"] == "user" else "assistant",
            "content": msg["text"]
        }
        for msg in history
    ]

@app.route('/chat', methods=['POST'])
def handle_chat():
    start_time = time.time()
    try:
        # 获取请求数据
        data = request.get_json()
        scenario = data.get('scenario')
        user_message = data.get('message')
        history = data.get('history', [])
        
        # 构建系统提示
        system_prompt = SCENARIO_PROMPTS.get(scenario, "請使用簡單粵語進行對話")
        
        # 构建请求payload
        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": system_prompt},
                *build_conversation_history(history),
                {"role": "user", "content": user_message}
            ],
            "temperature": 0.7,
            "max_tokens": 200  # 减少生成长度以加快响应
        }
        
        try:
            # 调用DeepSeek API（增加更详细的超时设置）
            response = requests.post(
                DEEPSEEK_API_URL,
                headers=headers,
                json=payload,
                timeout=(5, 120)  # 连接超时5秒，读取超时120秒
            )
        except requests.exceptions.Timeout as e:
            print(f"DeepSeek API超时详情: {str(e)}")
            return jsonify({"error": "对话响应超时，请重试"}), 504
        except Exception as e:
            print(f"API连接异常: {traceback.format_exc()}")
            return jsonify({"error": f"服务暂时不可用: {str(e)}"}), 500

        # 增加响应内容检查
        try:
            if response.status_code != 200:
                print(f"DeepSeek异常响应: {response.text[:500]}")
                
            response_data = response.json()
        except Exception as json_err:
            print(f"JSON解析失败: {str(json_err)} 原始响应: {response.text[:500]}")
            # 如果返回的数据不是 JSON 格式，则尝试把原始文本作为回复内容返回
            if response.text and response.text.strip() != "":
                response_data = {"choices": [{"message": {"content": response.text}, "finish_reason": "unknown"}]}
            else:
                return jsonify({"error": "响应解析失败", "detail": response.text[:200]}), 500

        # 处理可能被截断的回复
        ai_response = response_data.get('choices', [{}])[0].get('message', {}).get('content', '')
        finish_reason = response_data.get('choices', [{}])[0].get('finish_reason', 'unknown')
        
        if finish_reason == 'length':  # 添加截断提示
            ai_response += "\n（回复因长度限制被截断）"
            
        return jsonify({
            "response": ai_response,
            "scenario": scenario,
            "warning": "reply_truncated" if finish_reason == 'length' else ""
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": "系统处理异常"}), 500  # 隐藏具体错误细节
    finally:
        duration = time.time() - start_time
        print(f"聊天请求处理耗时: {duration:.2f}秒")

@app.route('/init', methods=['POST'])
def handle_init():
    start_time = time.time()
    try:
        client_ip = request.headers.get('X-Real-IP', request.remote_addr)
        print(f"\n=== 收到来自 {client_ip} 的初始化请求 ===")
        print(f"请求时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("请求头:", dict(request.headers))
        print("请求体:", request.get_data(as_text=True)[:500])
        
        data = request.get_json()
        prompt = data.get('prompt')
        
        if not prompt:
            return jsonify({"error": "缺少必要参数"}), 400

        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY.strip()}",  # 增加strip()处理
            "Content-Type": "application/json",
            "Accept-Encoding": "gzip"  # 新增压缩支持
        }
        
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": "你是一个粤语对话场景的引导者"},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 100  # 修改此值可以让AI回复更短
        }
        
        try:
            response = requests.post(
                DEEPSEEK_API_URL,
                headers=headers,
                json=payload,
                timeout=(5, 60)  # 连接超时5秒, 读取超时60秒
            )
        except requests.exceptions.Timeout as e:
            print(f"DeepSeek API超时详情: {str(e)}")
            return jsonify({"error": "对话响应超时，请重试"}), 504
        except requests.exceptions.ConnectionError as e:
            if "timed out" in str(e).lower():
                print(f"DeepSeek API read timeout: {str(e)}")
                return jsonify({"error": "对话响应超时，请重试"}), 504
            else:
                print(f"API连接异常: {traceback.format_exc()}")
                return jsonify({"error": "服务暂时不可用"}), 500

        # 增加响应状态检查
        print(f"DeepSeek API状态码: {response.status_code}")
        if response.status_code >= 400:
            print(f"DeepSeek错误响应头: {response.headers}")
            
        try:
            response_data = response.json()
        except Exception as json_err:
            response_data = response.text  # 无法解析为 JSON 则使用原始文本
        print("DeepSeek API返回状态码:", response.status_code)
        print("DeepSeek API响应内容:", response_data)
        
        if not response.ok:
            return jsonify({
                "error": f"API请求失败: {response.status_code}",
                "detail": response_data
            }), 500
            
        if isinstance(response_data, dict):
            ai_response = response_data.get('choices', [{}])[0].get('message', {}).get('content', "无法生成回复")
        else:
            ai_response = response_data

        return jsonify({
            "response": ai_response
        })
        
    except Exception as e:
        print(f"!!! 初始化完整错误堆栈:")
        traceback.print_exc()  # 打印完整堆栈信息
        return jsonify({"error": f"初始化失败: {str(e)}"}), 500
    finally:
        duration = time.time() - start_time
        print(f"请求处理耗时: {duration:.2f}秒")

@app.route('/health')
def health_check():
    """健康检查接口"""
    try:
        # 添加数据库连接检查（如果有）
        return jsonify({
            "status": "ok",
            "version": "1.0.0",
            "timestamp": datetime.now().isoformat()
        }), 200
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True) 