# Local Linux Hardware Q&A Assistant

A secure, local, natural-language conversational assistant that inspects a host Linux laptop's hardware specifications and answers queries with high precision. Instead of letting the LLM guess hardware specs, the system uses a deterministic, allow-listed tool-calling engine to execute read-only OS utilities and return normalized JSON data.

---

## Architecture & Core Engineering Design+-----------------------------------------------------------------+
|                    User Chat Interface (CLI)                    |
+-----------------------------------------------------------------+
|
v
+-----------------------------------------------------------------+
|               Google GenAI LLM Orchestration Engine             |
|          (Tool Selector & Strict Anti-Hallucination Prompt)     |
+-----------------------------------------------------------------+
|
(Structured Tool Call Request)
v
+-----------------------------------------------------------------+
|                 Safe Execution & Parsing Layer                  |
|  +--------------------+  +-------------------+  +------------+  |
|  | Static Command     |  | Privileged Helper |  | Robust     |  |
|  | Allow-List         |  | Fallback (WSL/DMI)|  | Parsers    |  |
|  +--------------------+  +-------------------+  +------------+  |
+-----------------------------------------------------------------+
|
(Normalized JSON Data)
v
+-----------------------------------------------------------------+
|                Final Response Generator (Gemini)                |
+-----------------------------------------------------------------+---

## Key Engineering Features

1. **Strict Security & Allow-Listing**: The LLM *never* generates arbitrary shell commands. It selects pre-defined tool identifiers mapped to static argument lists. Commands execute via `subprocess.run(..., shell=False)` with pinned absolute binary paths (`shutil.which()`) and `LC_ALL=C` locale pinning to prevent command injection, chaining, and locale-dependent parsing bugs.
2. **Privilege Escalation & WSL2 Portability**: 
   - On bare-metal Linux, privileged SMBIOS queries (`dmidecode`) utilize non-interactive `sudo -n` configured via scoped `sudoers.d` rules.
   - Inside virtualized environments (like WSL2), the engine automatically bridges to safe host-level PowerShell CIM queries (`Get-CimInstance`) so physical RAM slots, motherboard capacities, and NVMe drives are accurately reported without crashing.
3. **Anti-Hallucination & Upgrade Math**: System prompts strictly forbid guessing. Memory parsers pre-calculate exact upgrade metrics (`max_additional_ram_gb`, `free_slots`, `can_upgrade`) so the LLM outputs precise answers (e.g., *"You have 16 GB in 1 of 2 slots. The board supports up to 64 GB..."*).
4. **Session Caching & Multi-Turn Context**: Hardware command outputs are cached in session memory to avoid re-running slow OS subprocesses during conversational follow-up questions (*"and what about the GPU?"*).

---

## Project Structurelinux-hardware-assistant/
├── app/                  # (or src/)
│   ├── hardware/
│   │   ├── cpu.py        # lscpu & /proc/cpuinfo parser
│   │   ├── memory.py     # free, dmidecode, & WSL2 SMBIOS parser
│   │   ├── storage.py    # lsblk JSON & NVMe /sys/block parser
│   │   └── system.py     # lspci GPU & /sys/class/dmi/id parser
│   └── main.py           # GenAI chat loop, session cache, & retry handler
├── tools/
│   └── executor.py       # Allow-list security gatekeeper & subprocess runner
├── tests/
│   └── test_hardware.py  # pytest suite (security, upgrade math, parsers)
├── requirements.txt      # Python dependencies
└── README.md---

## Setup & Usage

### 1. Installation
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
### 2. Configure API key
export GEMINI_API_KEY="your-gemini-api-key-here"
export GEMINI_MODEL="gemini-3.5-flash-lite------Run Unit Tests
Bash
PYTHONPATH=. pytest -vRun the Assistant
Bash
PYTHONPATH=. python3 src/main.py---

### Step 2: Create `.env.example` and `.gitignore`
Keep your repository clean and ensure your API keys never get committed to GitHub:

```bash
cat << 'EOF' > .env.example
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-3.5-flash-lite
