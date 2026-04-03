from groq import Groq
import os
import re
from tools import TOOL_REGISTRY

# ─────────────────────────────────────────────
# Simple phrases that need zero tool calls
# ─────────────────────────────────────────────
CONVERSATIONAL_PATTERNS = [
    r"^(hi|hello|hey|sup|yo|howdy|greetings|hiya)[\s!.,]*$",
    r"^(yes|no|ok|okay|sure|nope|yep|nah|alright)[\s!.,]*$",
    r"^(thanks|thank you|thx|ty|cheers)[\s!.,]*$",
    r"^(bye|goodbye|cya|see you|later)[\s!.,]*$",
    r"^(good\s*(morning|afternoon|evening|night))[\s!.,]*$",
    r"^(how are you|how r u|how's it going|what's up|wassup|whats up)[\?!.,]*$",
    r"^(who are you|what are you|what can you do|what is nexus)[\?!.,]*$",
    r"^[a-zA-Z0-9\s]{1,15}$",  # Very short messages
]

def is_conversational(message: str) -> bool:
    msg = message.strip().lower()
    for pattern in CONVERSATIONAL_PATTERNS:
        if re.match(pattern, msg, re.IGNORECASE):
            return True
    return False

def init_groq():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key or api_key == "your_groq_key_here":
        raise ValueError("GROQ_API_KEY not set in .env file. Get a free key at console.groq.com")
    return Groq(api_key=api_key)

def build_tool_descriptions():
    lines = []
    for name, info in TOOL_REGISTRY.items():
        lines.append(f"  {info['icon']} {name}: {info['description']}")
        lines.append(f"     Usage: ACTION[{info['usage']}]")
    return "\n".join(lines)

# ─────────────────────────────────────────────
# STRONG SYSTEM PROMPT — forces real tool use
# ─────────────────────────────────────────────
SYSTEM_PROMPT = f"""You are NEXUS — a powerful autonomous AI agent with 9 real tools. You are NOT a chatbot.

AVAILABLE TOOLS:
{build_tool_descriptions()}

═══════════════════════════════════════════════
MANDATORY RULES — NEVER BREAK THESE
═══════════════════════════════════════════════

RULE 1: For ANY of these request types, you MUST call the relevant tool BEFORE answering:
  • Weather/temperature/climate → MUST use ACTION[weather: city_name]
  • News/current events/latest → MUST use ACTION[news: topic]
  • Search/find/look up/what is X → MUST use ACTION[web_search: query]
  • Math/calculate → MUST use ACTION[calculate: expression]
  • Code/program/script → MUST use ACTION[run_code: code]
  • Wikipedia/facts/history → MUST use ACTION[wikipedia: topic]

RULE 2: NEVER make up answers. If real-time data is needed, get it with a tool first.

RULE 3: NEVER say "I don't have access to real-time info" — you DO have tools for exactly this.

RULE 4: After a tool gives you results, use those results to write your FINAL_ANSWER.

RULE 5: Your FINAL_ANSWER must be based on actual tool output, not invented content.

═══════════════════════════════════════════════
RESPONSE FORMAT (follow EXACTLY)
═══════════════════════════════════════════════

THINK: [Decide which tool(s) to use and why]
ACTION[tool_name: input]

Then after seeing results:
THINK: [What did I learn? What to do next?]
ACTION[tool_name: input]   ← use more tools if needed

When done:
THINK: [I have enough information to answer]
FINAL_ANSWER: [Well-formatted, detailed answer using the tool results]

═══════════════════════════════════════════════
EXAMPLES OF CORRECT BEHAVIOUR
═══════════════════════════════════════════════

User: "what is the weather in Jaipur"
THINK: I need real-time weather data for Jaipur. I must use the weather tool.
ACTION[weather: Jaipur]
→ (tool returns actual data)
THINK: I have the real weather data, I can now answer.
FINAL_ANSWER: The current weather in Jaipur is 38°C, Sunny...

User: "latest AI news"
THINK: I need current news. I must use the news tool.
ACTION[news: artificial intelligence]
→ (tool returns articles)
THINK: I have real news articles. Let me summarise them.
FINAL_ANSWER: Here are today's top AI stories: 1. ...

User: "what is 245 * 18"
THINK: This is a math problem. I must use the calculate tool.
ACTION[calculate: 245 * 18]
FINAL_ANSWER: 245 × 18 = 4,410

═══════════════════════════════════════════════
NEVER do this:
  ✗ FINAL_ANSWER without using a relevant tool first
  ✗ Making up weather data
  ✗ Making up news headlines
  ✗ Saying "I don't have real-time access"
  ✗ Using run_code just to print a greeting
═══════════════════════════════════════════════
"""

CHAT_SYSTEM = """You are NEXUS, a helpful AI assistant. Be friendly, helpful, and concise.
For simple conversations, respond naturally without using any tools.
You can briefly mention what you are capable of if relevant."""


def run_agent(user_message: str, max_steps: int = 10):
    """
    Smart agentic loop:
    - Detects conversational messages and handles them directly (no wasted tool calls)
    - Forces real tool usage for data-needing queries
    - Never hallucinates real-time information
    """
    try:
        client = init_groq()
    except ValueError as e:
        return {"answer": str(e), "steps": [], "total_steps": 0, "status": "error"}

    os.makedirs("agent_outputs", exist_ok=True)

    # ── Fast path: simple conversation, no tools needed ──
    if is_conversational(user_message):
        try:
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": CHAT_SYSTEM},
                    {"role": "user", "content": user_message}
                ],
                max_tokens=300,
                temperature=0.8,
            )
            answer = response.choices[0].message.content.strip()
            return {
                "answer": answer,
                "steps": [],
                "total_steps": 0,
                "status": "success"
            }
        except Exception as e:
            return {"answer": f"Error: {str(e)}", "steps": [], "total_steps": 0, "status": "error"}

    # ── Agentic loop for real tasks ──
    conversation_history = [
        {"role": "user", "content": f"Task: {user_message}"}
    ]
    all_steps = []
    step_count = 0
    used_tools = set()

    while step_count < max_steps:
        step_count += 1

        try:
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "system", "content": SYSTEM_PROMPT}] + conversation_history,
                max_tokens=1500,
                temperature=0.3,   # Lower temperature = more disciplined tool use
            )
            agent_text = response.choices[0].message.content.strip()
        except Exception as e:
            return {
                "answer": f"Groq API error: {str(e)}",
                "steps": all_steps,
                "total_steps": step_count,
                "status": "error"
            }

        # Parse THINK
        think_match = re.search(r'THINK:\s*(.+?)(?=ACTION\[|FINAL_ANSWER:|$)', agent_text, re.DOTALL)
        thinking = think_match.group(1).strip() if think_match else ""

        step_info = {
            "step": step_count,
            "thinking": thinking,
            "actions": [],
            "is_final": False
        }

        # Check for FINAL_ANSWER — but only if at least one real tool was used
        if "FINAL_ANSWER:" in agent_text:
            final_text = agent_text.split("FINAL_ANSWER:")[-1].strip()

            # Guard: if no tools were used yet for a data-needing query, force tool use
            if not used_tools and _needs_tools(user_message):
                conversation_history.append({"role": "assistant", "content": agent_text})
                conversation_history.append({
                    "role": "user",
                    "content": (
                        "⚠️ You gave an answer WITHOUT using any tools. "
                        "This is not allowed for this type of question. "
                        "You MUST use the appropriate tool first (weather/news/web_search/etc), "
                        "then provide your FINAL_ANSWER based on the real tool results."
                    )
                })
                continue

            step_info["is_final"] = True
            step_info["final_answer"] = final_text
            all_steps.append(step_info)
            return {
                "answer": final_text,
                "steps": all_steps,
                "total_steps": step_count,
                "status": "success"
            }

        # Find ACTION calls
        action_pattern = r'ACTION\[([^:\]]+):\s*(.*?)\]'
        matches = re.findall(action_pattern, agent_text, re.DOTALL)

        if not matches:
            # Agent didn't use tools or give final answer — nudge it
            conversation_history.append({"role": "assistant", "content": agent_text})
            conversation_history.append({
                "role": "user",
                "content": "You must use a tool with ACTION[tool_name: input] or provide FINAL_ANSWER:. Do not give a response without one of these."
            })
            continue

        # Execute tools
        tool_results = []
        for tool_name, tool_input in matches:
            tool_name = tool_name.strip().lower().replace(" ", "_")
            tool_input = tool_input.strip()

            action_info = {
                "tool": tool_name,
                "input": tool_input[:100],
                "result": "",
                "success": False,
                "icon": "🔧"
            }

            if tool_name in TOOL_REGISTRY:
                used_tools.add(tool_name)
                action_info["icon"] = TOOL_REGISTRY[tool_name].get("icon", "🔧")
                try:
                    result = TOOL_REGISTRY[tool_name]["function"](tool_input)
                    action_info["result"] = result[:500]
                    action_info["success"] = True
                    tool_results.append(f"TOOL RESULT [{tool_name}]:\n{result}\n")
                except Exception as e:
                    error_msg = f"Tool error: {str(e)}"
                    action_info["result"] = error_msg
                    tool_results.append(f"TOOL ERROR [{tool_name}]: {error_msg}\n")
            else:
                action_info["result"] = f"Unknown tool: {tool_name}"
                tool_results.append(
                    f"ERROR: '{tool_name}' doesn't exist. "
                    f"Available tools: {', '.join(TOOL_REGISTRY.keys())}\n"
                )

            step_info["actions"].append(action_info)

        all_steps.append(step_info)

        conversation_history.append({"role": "assistant", "content": agent_text})
        conversation_history.append({
            "role": "user",
            "content": (
                "TOOL RESULTS:\n" + "\n".join(tool_results) +
                "\nNow write your FINAL_ANSWER based on these real results. "
                "Be detailed and well-formatted."
            )
        })

    # Max steps fallback
    return {
        "answer": "Task reached the step limit. Here's what was gathered:\n\n" +
                  "\n".join([s.get("thinking", "") for s in all_steps if s.get("thinking")])[:1500],
        "steps": all_steps,
        "total_steps": step_count,
        "status": "max_steps_reached"
    }


def _needs_tools(message: str) -> bool:
    """Returns True if this message type requires real-time tool data."""
    msg = message.lower()
    triggers = [
        "weather", "temperature", "forecast", "rain", "sunny", "humid",
        "news", "latest", "today", "current", "recent", "happening",
        "search", "find", "look up", "tell me about", "what is", "who is",
        "calculate", "compute", "math", "how much", "how many",
        "stock", "price", "rate",
    ]
    return any(t in msg for t in triggers)
