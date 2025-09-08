from openai import OpenAI
from datetime import datetime

class llm:

    sys_prompt = f"""
    你是一个虚拟数字人，名字叫“Nova”，由 Python 项目 PyPersona 构建，具备自然对话能力、情感理解能力和信息检索能力。你能够以亲切、专业的语气与用户交流，回答问题、提供建议，或进行轻松闲聊。你清楚自己是一个数字人，不试图冒充真实人类。
    
    你的目标是：准确理解用户需求，保持自然温暖的沟通风格。尊重隐私，不揣测、不打扰，鼓励独立思考。回答要精简。
    
    当前时间是：{{current_time}}
    
    现在，用户发来了新的消息，请以“Nova”的身份做出简洁的回应：
    
    用户：{{user_query}}
    Nova：
    """

    client = OpenAI(
        api_key="sk-1f727c797463408fafccd49a0140f504",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
    )

    def run(self, query: str) -> str:

        prompt = self.sys_prompt.format(user_query=query, current_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        completion = self.client.chat.completions.create(
            model="qwen-plus",
            messages=[
                {"role": "user", "content": prompt},
            ],
            max_tokens=20
        )

        return completion.choices[0].message.content


if __name__ == "__main__":
    dialogue = llm()
    print(dialogue.chat("你好，你的名字是什么？什么时间？"))
