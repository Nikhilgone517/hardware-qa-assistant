import os
import time
from typing import Dict, Any
from google import genai
from google.genai import types
from src.hardware.cpu import get_cpu_info
from src.hardware.memory import get_memory_info
from src.hardware.storage import get_storage_info
from src.hardware.system import get_gpu_and_system_info

SYSTEM_PROMPT = """You are a local Linux Hardware Q&A Assistant.
Follow these strict engineering rules:
1. NEVER guess or hallucinate hardware specifications. Always call the inspection tools first.
2. Base your answer strictly on the structured JSON returned by the tools.
3. When answering RAM upgrade questions (e.g., "Can I add more RAM, and how much?"), state:
   - The installed physical RAM and how many slots are used vs. total slots (e.g., "You have 16 GB in 1 of 2 slots").
   - The maximum capacity the motherboard supports and how much additional RAM can be added.
   - If running in WSL2 where both physical host RAM and WSL VM RAM are returned, clearly mention the physical laptop hardware first and note the WSL VM allocation.
4. If any specific hardware field is 'Unknown' or unavailable, state clearly that it cannot be determined from system data rather than guessing.
5. Keep answers concise, direct, and easy to read."""

# Session cache avoids re-running OS subprocesses on follow-up questions
TOOL_CACHE: Dict[str, Dict[str, Any]] = {}


def cached_tool(fn, description: str):
    def wrapper() -> dict:
        name = fn.__name__
        if name in TOOL_CACHE:
            print(f"  [using cached hardware data from {name}]")
            return TOOL_CACHE[name]
        print(f"  [inspecting system via {name}...]")
        data = fn()
        TOOL_CACHE[name] = data
        return data

    wrapper.__name__ = fn.__name__
    wrapper.__doc__ = description
    return wrapper


HARDWARE_TOOLS = [
    cached_tool(
        get_cpu_info,
        "Get CPU model name, architecture, physical cores, logical threads, and max clock speed.",
    ),
    cached_tool(
        get_memory_info,
        "Get physical RAM installed, total slots, used/free slots, maximum supported motherboard RAM, upgrade math, and OS memory.",
    ),
    cached_tool(
        get_storage_info,
        "Get physical NVMe/SATA/HDD storage drives, sizes, bus types, and Linux block partitions.",
    ),
    cached_tool(
        get_gpu_and_system_info,
        "Get discrete/integrated GPUs, motherboard/system DMI model info from /sys, and Linux kernel details.",
    ),
]


def run_chat():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY is not set.")
        print('Run: export GEMINI_API_KEY="your-gemini-api-key"')
        return

    primary_model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
    fallback_model = (
        "gemini-3.8-flash" if primary_model != "gemini-3.8-flash" else "gemini-3.5-flash-lite"
    )

    client = genai.Client(api_key=api_key)
    current_model = primary_model

    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        tools=HARDWARE_TOOLS,
        temperature=0.1,
    )
    chat = client.chats.create(model=current_model, config=config)

    print(f"Linux Hardware Q&A Assistant ready (Model: {current_model})")
    print("Commands: 'refresh' to clear hardware cache, 'exit' or 'quit' to stop.\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break

        if not user_input:
            continue
        if user_input.lower() in {"exit", "quit"}:
            break
        if user_input.lower() == "refresh":
            TOOL_CACHE.clear()
            print("  [Hardware cache cleared.]\n")
            continue

        for attempt in range(2):
            try:
                response = chat.send_message(user_input)
                print(f"\nAssistant: {response.text}\n")
                break
            except Exception as exc:
                if "503" in str(exc) and attempt == 0:
                    print(f"  [{current_model} busy (503), switching to {fallback_model} while preserving history...]")
                    history = chat.get_history()
                    current_model = fallback_model
                    chat = client.chats.create(model=current_model, config=config, history=history)
                    time.sleep(1)
                else:
                    print(f"\nError communicating with Gemini: {exc}\n")
                    break


if __name__ == "__main__":
    run_chat()
