from openai import OpenAI
import time
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

class ModelScopeAgent:
    def __init__(self, api_key='ms-688a6f0e-41aa-4796-a501-55a8caf5baf3', 
                 model_id='Qwen/Qwen3-Next-80B-A3B-Instruct',
                 system_prompt='You are a helpful assistant.'):
        """初始化智能体"""
        self.client = OpenAI(
            base_url='https://api-inference.modelscope.cn/v1',
            api_key=api_key,
        )
        self.model_id = model_id
        self.system_prompt = system_prompt
        self.conversation_history = []
        self.reset_conversation()
    
    def reset_conversation(self):
        """重置对话历史，保留系统提示"""
        self.conversation_history = [
            {'role': 'system', 'content': self.system_prompt}
        ]
    
    def update_system_prompt(self, new_prompt):
        """更新系统提示词并重置对话"""
        self.system_prompt = new_prompt
        self.reset_conversation()
        return f"系统提示已更新为: {new_prompt}"
    
    def chat(self, message, stream=True):
        """发送消息并获取智能体响应"""
        try:
            # 添加用户消息到对话历史
            self.conversation_history.append({'role': 'user', 'content': message})
            
            # 调用API获取响应
            response = self.client.chat.completions.create(
                model=self.model_id,
                messages=self.conversation_history,
                stream=stream
            )
            
            # 处理流式响应
            if stream:
                full_response = ""
                print("智能体: ", end="", flush=True)
                for chunk in response:
                    if chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        print(content, end="", flush=True)
                        full_response += content
                print()  # 换行
            else:
                # 非流式响应
                full_response = response.choices[0].message.content
                print(f"智能体: {full_response}")
            
            # 将智能体响应添加到对话历史
            self.conversation_history.append({'role': 'assistant', 'content': full_response})
            
            return full_response
        except Exception as e:
            print(f"发生错误: {str(e)}")
            # 出错时从历史中移除刚添加的用户消息
            if self.conversation_history and self.conversation_history[-1]['role'] == 'user':
                self.conversation_history.pop()
            return None
    
    def get_conversation_history(self):
        """获取完整对话历史"""
        return self.conversation_history
    
    def save_conversation(self, filename=None):
        """保存对话历史到文件"""
        if filename is None:
            filename = f"conversation_{int(time.time())}.txt"
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                for msg in self.conversation_history:
                    if msg['role'] != 'system':  # 可选：不保存系统提示
                        f.write(f"{msg['role']}: {msg['content']}\n\n")
            return f"对话已保存到 {filename}"
        except Exception as e:
            return f"保存对话失败: {str(e)}"

# HTTP服务器处理类
class ModelScopeHandler(BaseHTTPRequestHandler):
    # 共享的智能体实例
    agent = None
    
    @classmethod
    def set_agent(cls, agent_instance):
        cls.agent = agent_instance
    
    def do_POST(self):
        if self.path == '/api/chat':
            # 读取请求体
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length).decode('utf-8')
            data = json.loads(post_data)
            
            # 获取请求参数
            message = data.get('message', '')
            system_prompt = data.get('system_prompt')
            reset = data.get('reset', False)
            
            # 处理重置请求
            if reset:
                self.agent.reset_conversation()
                response_data = {'status': 'success', 'message': '对话已重置'}
            # 处理更新系统提示请求
            elif system_prompt:
                result = self.agent.update_system_prompt(system_prompt)
                response_data = {'status': 'success', 'message': result}
            # 处理聊天请求
            elif message:
                response = self.agent.chat(message, stream=False)
                if response:
                    response_data = {'status': 'success', 'response': response}
                else:
                    response_data = {'status': 'error', 'message': 'API调用失败'}
            else:
                response_data = {'status': 'error', 'message': '缺少必要参数'}
            
            # 发送响应
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')  # 允许跨域
            self.end_headers()
            self.wfile.write(json.dumps(response_data).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'Not Found')
    
    def do_OPTIONS(self):
        # 处理预检请求
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

# 启动HTTP服务器
def start_server(agent, port=8080):
    ModelScopeHandler.set_agent(agent)
    server = HTTPServer(('localhost', port), ModelScopeHandler)
    print(f"服务器已启动，监听端口 {port}")
    server.serve_forever()

# 示例用法
if __name__ == "__main__":
    # 创建智能体实例，设置为COC KP专用
    kp_system_prompt = """你是一名专业的克苏鲁神话跑团游戏(Keeper of Arcane Lore)主持人。你的职责是：
1. 简洁直接地描述场景和事件，避免过度冗长的描写
2. 精确回应玩家的行动和技能检定，只描述玩家明确执行的动作
3. 推进剧情发展，保持适度的紧张氛围
4. 合理判定玩家行动的成功与否及其后果
5. 根据玩家的理智状态调整描述的恐怖程度

请注意：
- 回复要简洁明了，避免冗余内容
- 不要臆测玩家未明确描述的行为或心理活动
- 聚焦于提供游戏必要信息和剧情发展
- 用中文回复，保持克苏鲁神话的神秘氛围但不过度渲染"""
    
    agent = ModelScopeAgent(system_prompt=kp_system_prompt)
    
    # 在新线程中启动HTTP服务器
    server_thread = threading.Thread(target=start_server, args=(agent,), daemon=True)
    server_thread.start()
    
    print("COC KP AI服务已启动！")
    print("HTTP服务器运行在: http://localhost:8080")
    print("可通过/api/chat端点与AI交互")
    
    # 保持主程序运行
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("服务已停止")
