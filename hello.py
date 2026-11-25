import os, json
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI()
MODEL = os.getenv("OPENAI_MODEL")

resp = client.chat.completions.create(
    model=MODEL,
    messages=[{
        "role": "user",
        "content": 'Return only JSON: {"answer": <a one-sentence definition of LLM>}',
    }],
    response_format={"type": "json_object"},
)
text = resp.choices[0].message.content
print(text)
print(json.loads(text)["answer"])
print(resp.usage.prompt_tokens, resp.usage.completion_tokens)