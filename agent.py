import os, sys, json
from dotenv import load_dotenv
from openai import OpenAI
from tools import TOOL_DEFS, run_tool

load_dotenv()
client = OpenAI()
MODEL = os.getenv("OPENAI_MODEL")
MAX_STEPS = 6
SYSTEM = ("You answer questions about a hospital database using the tools. "
          "Call describe_tables first if you are unsure of the schema. "
          "Only state numbers returned by a tool. If the data cannot answer "
          "the question, say so instead of guessing.")

def ask(question):
    messages = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": question}]
    for step in range(MAX_STEPS):
        resp = client.chat.completions.create(
            model=MODEL, messages=messages, tools=TOOL_DEFS)
        msg = resp.choices[0].message
        messages.append(msg)
        if not msg.tool_calls:          # 模型直接回答,结束
            return msg.content
        for call in msg.tool_calls:
            args = json.loads(call.function.arguments)
            out = run_tool(call.function.name, args)
            print(f"[step {step}] {call.function.name} {args}")
            messages.append({"role": "tool",
                             "tool_call_id": call.id,
                             "content": out})
    return "Stopped: reached the maximum number of steps."

if __name__ == "__main__":
    print(ask(sys.argv[1]))