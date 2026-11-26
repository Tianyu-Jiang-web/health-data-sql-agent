import os, sys, json, time, uuid
from datetime import datetime, timezone
from dotenv import load_dotenv
from openai import OpenAI
from tools import TOOL_DEFS, run_tool

load_dotenv()
client = OpenAI()
MODEL = os.getenv("OPENAI_MODEL")
MAX_STEPS = 6
PRICE_IN = float(os.getenv("PRICE_INPUT_PER_M", "0"))
PRICE_OUT = float(os.getenv("PRICE_OUTPUT_PER_M", "0"))
LOG_PATH = "logs/agent_log.jsonl"

SYSTEM_V1 = ("You answer questions about a hospital database using the tools. "
             "Call describe_tables first if you are unsure of the schema. "
             "Only state numbers returned by a tool. If the data cannot answer "
             "the question, say so instead of guessing.")

SYSTEM_V2 = SYSTEM_V1 + (
    " Before filtering on a text column, run SELECT DISTINCT on that column "
    "to see how its values are actually written. "
    "Each row in patients is one patient; each row in admissions is one "
    "hospital admission, and one patient can have several admissions, so "
    "never report an admission count as a patient count. "
    "Compute rates and averages inside SQL instead of by hand. "
    "If the question is too vague to answer with one query, say what is "
    "unclear and ask the user to clarify instead of guessing.")

PROMPTS = {"v1": SYSTEM_V1, "v2": SYSTEM_V2}
PROMPT_VERSION = os.getenv("PROMPT_VERSION", "v1")
SYSTEM = PROMPTS[PROMPT_VERSION]

def write_log(record):
    os.makedirs("logs", exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

def ask(question):
    start = time.time()
    messages = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": question}]
    steps = []
    answer = None
    status = "max_steps"           # 默认:循环用完都没答出来

    for step in range(MAX_STEPS):
        t0 = time.time()
        try:
            resp = client.chat.completions.create(
                model=MODEL, messages=messages, tools=TOOL_DEFS)
        except Exception as e:
            status = "api_error"
            answer = f"API error: {e}"
            break

        msg = resp.choices[0].message
        messages.append(msg)
        info = {"step": step,
                "latency_s": round(time.time() - t0, 2),
                "prompt_tokens": resp.usage.prompt_tokens,
                "completion_tokens": resp.usage.completion_tokens,
                "tool_calls": []}
        steps.append(info)

        if not msg.tool_calls:      # 模型直接回答,结束
            answer = msg.content
            status = "answered"
            break

        for call in msg.tool_calls:
            try:
                args = json.loads(call.function.arguments)
                out = run_tool(call.function.name, args)
            except Exception as e:  # 参数不是合法 JSON、缺字段等
                args = call.function.arguments
                out = f"Error: could not run tool: {e}"
            info["tool_calls"].append({
                "name": call.function.name,
                "args": args,
                "error": out.startswith("Error")})
            print(f"[step {step}] {call.function.name} {args}")
            messages.append({"role": "tool",
                             "tool_call_id": call.id,
                             "content": out})

    if answer is None:
        answer = "Stopped: reached the maximum number of steps."

    p_tok = sum(s["prompt_tokens"] for s in steps)
    c_tok = sum(s["completion_tokens"] for s in steps)
    record = {
        "run_id": str(uuid.uuid4())[:8],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model": MODEL,
        "prompt_version": PROMPT_VERSION,
        "question": question,
        "answer": answer,
        "status": status,
        "n_steps": len(steps),
        "latency_s": round(time.time() - start, 2),
        "prompt_tokens": p_tok,
        "completion_tokens": c_tok,
        "est_cost_usd": round(p_tok / 1e6 * PRICE_IN + c_tok / 1e6 * PRICE_OUT, 6),
        "steps": steps,
    }
    write_log(record)
    return record

if __name__ == "__main__":
    rec = ask(sys.argv[1])
    print(rec["answer"])
    print(f"\n[{rec['status']}] steps={rec['n_steps']} "
          f"time={rec['latency_s']}s tokens={rec['prompt_tokens']}+{rec['completion_tokens']} "
          f"cost≈${rec['est_cost_usd']}")