from flask import Flask, request, jsonify, abort, send_file
import requests
from dotenv import load_dotenv
import os
from flask_cors import CORS
import time
from datetime import datetime
import traceback
import json
from flask_sock import Sock
import io
import edge_tts

# 修改后 (直接读取系统环境变量)
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
if not DEEPSEEK_API_KEY:
    raise ValueError("未配置 DEEPSEEK_API_KEY 环境变量")

load_dotenv()

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})  # 允许所有域名
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
sock = Sock(app)

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

@app.route('/tts', methods=['POST'])
def handle_tts():
    data = request.get_json()
    if not data or 'text' not in data:
        return jsonify({"error": "Missing 'text' field"}), 400
    text = data['text']
    if not text or len(text) > 500:  # 防止过长的文本
        return jsonify({"error": "Invalid text"}), 400
    voice = data.get('voice', "zh-HK-WanLungNeural")
    try:
        communicate = edge_tts.Communicate(text, voice)
        buf = io.BytesIO()
        for chunk in communicate.stream_sync():
            if chunk["type"] == "audio":
                buf.write(chunk["data"])
        buf.seek(0)
        return send_file(buf, mimetype='audio/mpeg')
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@sock.route('/ws/chat')
def chat_socket(ws):
    try:
        # 强制设置无扩展的响应头
        ws.handshake_response = lambda: (
            "HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Accept: {ws._get_accept_hash()}\r\n"
            "\r\n"
        )
        
        # 检查并拒绝压缩扩展请求
        if 'permessage-deflate' in ws.environ.get('HTTP_SEC_WEBSOCKET_EXTENSIONS', ''):
            print("检测到不支持的压缩扩展请求")
            abort(400, 'Compression not supported')
            
        while True:
            data = ws.receive()
            # 增加空消息检查
            if not data or data == 'ping':  # 合并判断条件
                if data == 'ping':
                    ws.send('pong')
                continue
            # 增加内容非空检查
            try:
                req_data = json.loads(data)
                if not req_data.get('message'):
                    ws.send(json.dumps({"error": "消息内容不能为空"}))
                    continue
            except json.JSONDecodeError:
                continue  # 已存在的错误处理

            scenario = req_data.get('scenario')
            user_message = req_data.get('message')
            history = req_data.get('history', [])
            
            system_prompt = SCENARIO_PROMPTS.get(scenario, "請使用簡單粵語進行對話")
            
            headers = {
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json"
            }
            payload = {
                 "model": "deepseek-chat",
                 "messages": (
                     [{"role": "system", "content": system_prompt}] +
                     build_conversation_history(history) +
                     [{"role": "user", "content": user_message}]
                 ),
                 "temperature": 0.7,
                 "max_tokens": 200,
                 "stream": True  # 启用流式输出
            }
            try:
                r = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, stream=True, timeout=(5, 120))
                buffer = ""  # 新增缓冲区处理不完整数据
                for line in r.iter_content(chunk_size=1024):
                    buffer += line.decode('utf-8')
                    while '\n' in buffer:
                        line, buffer = buffer.split('\n', 1)
                        if line.startswith('data:'):
                            try:
                                chunk = json.loads(line[len('data:'):].strip())
                                if chunk.get('choices'):
                                    content = chunk['choices'][0]['delta'].get('content', '')
                                    if content:
                                        # 直接发送文本内容
                                        ws.send(content)
                            except Exception as chunk_error:
                                print(f"块处理错误: {chunk_error}")
                # 发送结束信号
                ws.send(json.dumps({"status": "done"}))
            except Exception as e:
                print(f"流式请求错误: {traceback.format_exc()}")
                ws.send(json.dumps({"error": str(e)}))
            
    except Exception as e:
        print(f"WebSocket异常: {traceback.format_exc()}")
    finally:
        print("WebSocket连接关闭")

@app.before_request
def log_request_info():
    if request.path == '/ws/chat':
        print(f"\n=== WebSocket 握手请求头 ===")
        print("Connection:", request.headers.get('Connection'))
        print("Upgrade:", request.headers.get('Upgrade'))
        print("Sec-WebSocket-Key:", request.headers.get('Sec-WebSocket-Key'))

if __name__ == "__main__":
    # 更新默认端口为 5000（与 Nginx 代理配置对应）
    port = int(os.getenv("PORT", 5000))
    # 去掉 ssl_context 参数，使用纯 HTTP 方式启动
    app.run(host="0.0.0.0", port=port, threaded=False)

# 在Flask应用配置中添加
app.config['SOCK_SERVER_OPTIONS'] = {
    'ping_interval': 25,  # 与微信心跳间隔一致
    'ping_timeout': 5
} 