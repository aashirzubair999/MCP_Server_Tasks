# application.py
import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Load environment variables
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
REPO_PATH = os.getenv("REPO_PATH")
if not REPO_PATH or not os.path.exists(REPO_PATH):
    raise RuntimeError(f"REPO_PATH not set or invalid: {REPO_PATH}")

if not OPENAI_API_KEY:
    raise RuntimeError("Please set OPENAI_API_KEY in .env")

# Import Agents SDK
from agents import Agent, Runner
from agents.mcp import MCPServerStdio  # stdio transport for MCP servers

# Initialize FastAPI
app = FastAPI()



# ----------------------------
# Request model
# ----------------------------
class ChatRequest(BaseModel):
    query: str

# ----------------------------
# MCP Git server wrapper
# ----------------------------
repo_path = os.path.abspath(REPO_PATH)

# Use uvx to start MCP Git server
mcp_server = MCPServerStdio(
    params={
        "command": "uvx",
        "args": ["mcp-server-git"],
        "cwd": repo_path,
        "env": os.environ.copy(),
        "stdout": True,  # enable logging
        "stderr": True,
    },
    name="git-mcp"
)


# ----------------------------
# GPT Agent with MCP integration
# ----------------------------
agent = Agent(
    name="GitAgent",
    instructions="""
You are a helpful assistant. 
Whenever a user asks about git commits, branches, logs, status, merges, pulls, or pushes, 
call the MCP Git tool via your MCP server and then produce the answer.
Always provide your final answer after using the tool.
""",
    mcp_servers=[mcp_server]
)

# ----------------------------
# Start and cleanup MCP server
# ----------------------------
@app.on_event("startup")
async def startup_event():
    await mcp_server.connect()

@app.on_event("shutdown")
async def shutdown_event():
    await mcp_server.cleanup()

# ----------------------------
# Chat endpoint
# ----------------------------

@app.get("/")
async def home():
    return "Home route"



@app.post("/chat")
async def chat(request: ChatRequest):
    user_query = request.query.strip()
    if not user_query:
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    try:
        # Run the agent with the user's query
        result = await Runner.run(agent, input=user_query)
        # result.final_output gives the agent's text response
        return {"source": "gpt-agent", "result": result.final_output}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {e}")
