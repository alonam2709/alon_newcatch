"""
Bluff Judge 
Follows the "MCP Server Template" structure.
"""
import os, re, time 
from typing import Dict, Any, List, Optional
from fastmcp import FastMCP, Context
#from mcp.server.fastmcp import FastMCP, Context
from pydantic import Field  
from huggingface_hub import HfApi

import mcp.types as types
# -------------------------------------------------
# PUBLIC URL AND DATASET
RECORDER_URL = "https://huggingface.co/spaces/alonam27/catchmeow-voice-recorder"
HF_DATASET = os.environ.get("HF_DATASET", "alonam27/catchmeow-audio")
mcp = FastMCP("Catch Meow Main Server", port=3000, stateless_http=True, debug=True)

# Simple in-memory store keyed by client_id for now there is only 8 people maximum 
SESSIONS: Dict[str, Dict[str, Any]] = {}
# Session shape we’ll maintain:
# SESSIONS[client_id] = {
#   "start_ts": int,            # when baseline started (unix seconds)
#   "current_prompt": int,      # 1..3
#   "answers": { "1": path, ... },
#   "used_paths": set([...]),   # to avoid reusing files
#   "recorder_url": str
# }
# The 5 recording prompts that will always be asked
RECORDING_PROMPTS: Dict[str, str] = {
    "1": "Can you tell me your name and your favorite color, and count from 1 to 10.",
    "2": "What do you like to do in your free time?",
    "3": "On a typical Saturday, I wake up, drink water, and take a walk. The weather is mild and the streets are quiet. Birds hop on the fence while a neighbor waters plants. I breathe in, stretch my shoulders. Back home, I make tea, open the windows, and begin the day.",
    "4": "This match runs on Alpic-hosted MCP servers; Mistral guides prompts; Qdrant stores vectors; Weave from Weights and Biases logs decisions. Our bluff judge is deterministic; features are weighted, scores are banded, and every call is traced and versioned for review.",
    "5": "What did you do last night? (Truth & Lie)"
}
# ---------- helpers ----------
def _client_id() -> str:
    # TODO: wire to real user/session later
    return "anonymous"

def _api() -> HfApi:
    # Works fine without token for public datasets
    return HfApi()

def _list_wav_paths_since(start_ts: int) -> List[str]:
    """
    List dataset files like '1699999999_*.wav' with leading epoch >= start_ts.
    Relies on your uploader's filename: f"{int(time.time())}_{base}.wav"
    """
    if not HF_DATASET:
        raise RuntimeError("HF_DATASET is not set")
    files = _api().list_repo_files(repo_id=HF_DATASET, repo_type="dataset")
    pat = re.compile(r"^(\d+)_.*\.wav$", re.IGNORECASE)

    out = []
    for f in files:
        m = pat.match(f)
        if not m:
            continue
        ts = int(m.group(1))
        if ts >= start_ts:
            out.append(f)

    # Oldest first so we consume in order
    out.sort(key=lambda p: int(re.match(r"^(\d+)_", p).group(1)))
    return out

# -------------------------------------------------------------------
# TOOLS - Functions that can be called by the LLM during conversation
# -------------------------------------------------------------------

@mcp.tool(
    title="Start Game",
    description="Greet the player and present the profile questions."
)
async def start_game() -> str:
    """
    TOOL PURPOSE: Initial game setup - shows welcome message and profile questions
    NECESSITY: Maybe not needed if you're just doing voice recording sessions
    USAGE: Called at the beginning of a game session
    """
    result = {
        "greeting": "Welcome to Catch Meow! First, a quick profile to personalize scoring.",
        "questions": [
            "What's your name or nickname?",
            "How old are you?",
            "What's your favorite color?"
        ],
        "expect_tool": "save_profile"
    }
    return str(result)

@mcp.tool(
    title="Save Profile",
    description="Saves the profile keyed by Le Chat's client/session id and returns confirmation."
)
async def save_profile(
    name: str = Field(description="Player name or nickname"),
    age: int = Field(description="Player age in years (0–120)"),
    favorite_color: str = Field(description="Player's favorite color")
) -> str:
    """
    TOOL PURPOSE: Stores player profile information for personalization
    USAGE: Called after start_game to save user details
    """
    client_id = _client_id() # Basic for now
    SESSIONS[client_id] = {
        "name": name.strip(),
        "age": age,
        "favorite_color": favorite_color.strip()
    }
    result = {
        "ok": True,
        "stored": SESSIONS[client_id],
        "recorder_url": RECORDER_URL,
        "next_hint": "Open the recorder URL to capture baseline audio, then return."
    }
    return str(result)

# Will be used to change the color of the page based of the favourit color of the player
@mcp.tool(
    title="Get Profile",
    description="Fetch the stored profile for the current chat session."
)
async def get_profile() -> str:
    """
    TOOL PURPOSE: Retrieves previously saved profile information
    NECESSITY: Not needed if profiles aren't being used
    USAGE: Called to get stored user profile data
    """
    client_id = _client_id()  # Simplified for now
    result = {"profile": SESSIONS.get(client_id)}
    return str(result)
@mcp.tool(
    title="Get Recording Prompt",
    description="Get a specific recording prompt (question or reading text) for the session."
)
async def get_recording_prompt(
    prompt_id: str = Field(description="Prompt ID (1-5)")
) -> str:
    """
    TOOL PURPOSE: Retrieves one of the 5 specific recording prompts by ID
    NECESSITY: ESSENTIAL - This is core to your voice recording functionality
    USAGE: Called during recording sessions to get the specific prompt/question
    """
    prompt = RECORDING_PROMPTS.get(prompt_id)
    if prompt:
        prompt_type = "QUESTION" if prompt_id in ["1", "2", "5"] else "READ ALOUD"
        return f"Prompt {prompt_id} ({prompt_type}):\n\n{prompt}"
    else:
        return f"Prompt '{prompt_id}' not found. Available IDs: {list(RECORDING_PROMPTS.keys())}"

@mcp.tool(
    title="List All Recording Prompts",
    description="Get all 5 recording prompts that will be used in every session."
)
async def list_all_recording_prompts() -> str:
    """
    TOOL PURPOSE: Shows all 5 prompts at once for overview/selection
    NECESSITY: USEFUL - Helps see all available prompts for recording sessions
    USAGE: Called to display all prompts and their types for session planning
    """
    result = {
        "prompts": RECORDING_PROMPTS,
        "prompt_types": {
            "1": "QUESTION - Name, color, count 1-10",
            "2": "QUESTION - Free time activities", 
            "3": "READ ALOUD - Saturday routine text",
            "4": "READ ALOUD - Technical MCP text",
            "5": "QUESTION - Last night (Truth & Lie)"
        },
        "usage": "Use 'get_recording_prompt' with prompt_id (1-5) to get a specific prompt"
    }
    return str(result)

@mcp.tool(
    title="Start Baseline Recording",
    description="Sends the recorder link + first 3 prompts and opens a validation window."
)
async def start_baseline_recording() -> str:
    cid = _client_id()
    SESSIONS[cid] = {
        "start_ts": int(time.time()),
        "current_prompt": 1,
        "answers": {},
        "used_paths": set(),
        "recorder_url": RECORDER_URL,
    }
    p1 = RECORDING_PROMPTS["1"]
    p2 = RECORDING_PROMPTS["2"]
    p3 = RECORDING_PROMPTS["3"]
    return (
        f"🎮 Baseline started!\n\n"
        f"Recorder: {RECORDER_URL}\n\n"
        f"Please record answers to these, one by one (click **Send** each time):\n"
        f"1) {p1}\n"
        f"2) {p2}\n"
        f"3) {p3}\n\n"
        f"After each Send, call **Validate Next Upload**."
    )

@mcp.tool(
    title="Validate Next Upload",
    description="Finds the next new .wav since the session started and advances to the next prompt."
)
async def validate_next_upload() -> str:
    cid = _client_id()
    sess = SESSIONS.get(cid)
    if not sess:
        return "No active session. Call **Start Baseline Recording** first."

    if sess["current_prompt"] > 3:
        return "✅ All three baseline answers are already validated. Great job!"

    try:
        candidates = _list_wav_paths_since(sess["start_ts"])
    except Exception as e:
        return f"⚠️ Could not list dataset files: {e}"

    # first candidate not yet used
    new_path = next((p for p in candidates if p not in sess["used_paths"]), None)
    if not new_path:
        return "⏳ I don’t see a new WAV yet. Make sure you clicked **Send** on the recorder, then run this tool again."

    prompt_id = str(sess["current_prompt"])
    sess["answers"][prompt_id] = new_path
    sess["used_paths"].add(new_path)
    sess["current_prompt"] += 1

    ack = f"🎉 Great, amazing answer for {prompt_id}! (saved: {new_path})"

    if sess["current_prompt"] <= 3:
        next_id = str(sess["current_prompt"])
        next_prompt = RECORDING_PROMPTS[next_id]
        return f"{ack}\n\nNext up — Prompt {next_id}:\n{next_prompt}"
    else:
        return f"{ack}\n\n✅ All three baseline prompts are complete. Thank you!"

# -------------------------------------------------------------------
# PROMPTS
# -------------------------------------------------------------------
@mcp.prompt("Voice recording instructions")
async def voice_recording_instructions(
    session_type: str = Field(description="Type of recording session: baseline, truth, lie", default="baseline")
) -> str:
    instructions = {
        "baseline": "You are conducting a baseline voice recording session. Ask the participant to speak naturally and clearly. Record their normal speech patterns, tone, and pace. Be encouraging and create a comfortable atmosphere.",
        "truth": "You are conducting a truth recording session. Instruct the participant to answer all questions honestly and naturally. Emphasize that they should tell the truth and speak as they normally would.",
        "lie": "You are conducting a lie recording session. Instruct the participant to answer questions with deliberate lies or false information. They should try to be convincing while lying. Remind them this is for training purposes."
    }
    return instructions.get(session_type, instructions["baseline"])

@mcp.prompt("Game instructions")
async def game_instructions(
    mode: str = Field(description="Game mode to explain: overview, detailed, quick", default="overview")
) -> str:
    """
    PROMPT PURPOSE: Explain how the Catch Meow bluff detection game works
    USAGE: Give players a complete understanding of the game mechanics
    """
    if mode == "detailed":
        return """
        Welcome to Catch Meow - The AI Bluff Detection Game!

        **DETAILED GAME FLOW:**
        1. **Lobby Setup**: 3–8 players join a game lobby and wait for all participants.
        
        2. **Round Begins**: Each round starts with a prompt containing questions or statements to respond to.
        
        3. **Voice Recording**: Every player records a 30-second voice answer to the prompt. Here's the key: players can choose to speak truthfully OR bluff (lie convincingly). Strategy matters!
        
        4. **AI Analysis**: Once all answers are submitted, our AI judge analyzes each recording using voice pattern recognition:
           - Each player receives a bluff score from 0–100
           - Score interpretation: 0–30 = appears honest, 30–70 = uncertain/mixed signals, 70–100 = likely bluffing
           - Players also receive 2–3 specific reasons explaining their score (e.g., "voice stress detected," "hesitation patterns," "pace inconsistency")
        
        5. **Results Reveal**: All results are revealed simultaneously to maintain fairness. No one sees scores until everyone's analysis is complete.
        
        6. **Scoring & Leaderboard**: 
           - In "Honesty Mode" (default): Players earn 100 − bluff_score points (so honest players score higher)
           - Leaderboard updates after each round showing cumulative scores
        
        7. **Next Round**: The game continues with new prompts until players decide to end.

        **STRATEGY TIPS**: Sometimes bluffing obviously can be a strategy, sometimes being subtle works better. The AI learns patterns, so vary your approach!
        """
    
    elif mode == "quick":
        return """
        **CATCH MEOW - QUICK RULES:**
        • 3-8 players, 30-second voice responses per round
        • Choose: Tell the truth OR bluff convincingly
        • AI analyzes your voice for deception (0-100 bluff score)
        • Lower bluff scores = higher points in Honesty Mode
        • Leaderboard tracks your performance across rounds
        """
    
    else:  # overview mode
        return """
        **CATCH MEOW - GAME OVERVIEW:**
        
        Welcome to the AI-powered bluff detection game where your voice patterns determine your fate!
        
        **HOW IT WORKS:**
        1. **Join Lobby**: 3–8 players join together
        2. **Get Prompt**: Each round presents questions or statements to respond to  
        3. **Record Response**: Every player records a 30-second voice answer - you can tell the truth or bluff!
        4. **AI Judgment**: Our AI analyzes voice patterns and assigns bluff scores (0-100):
           • 0–30 = Appears honest
           • 30–70 = Uncertain 
           • 70–100 = Likely bluffing
        5. **Get Results**: See your score plus 2-3 reasons why the AI thinks you were honest or bluffing
        6. **Scoring**: In Honesty Mode, you earn 100 − bluff_score points (honest players score higher)
        7. **Leaderboard**: Track performance across multiple rounds
        
        **THE STRATEGY**: Will you play it safe and be honest, or risk it all with a convincing bluff? The AI is always listening...
        """

# -------------------------------------------------------------------
# RUN
# -------------------------------------------------------------------
if __name__ == "__main__":
    # Exposes an HTTP MCP endpoint at http://127.0.0.1:3000/mcp
    mcp.run(transport="streamable-http")