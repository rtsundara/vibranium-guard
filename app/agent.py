import os
import sys
from dotenv import load_dotenv

# Ensure environment variables are loaded
load_dotenv(override=True)

from google.adk.agents import LlmAgent
from google.adk.workflow import Workflow, FunctionNode, node, START
from google.adk.events.event import Event
from google.adk.agents.context import Context
from google.adk.models import Gemini
from google.genai import types
from pydantic import BaseModel, Field
from typing import Any

from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters

from .tools import get_log_entry

# Initialize the Model
# Using gemini-2.5-flash for reliability and performance
gemini_model = Gemini(
    model="gemini-2.5-flash", 
    retry_options=types.HttpRetryOptions(attempts=3),
)

# Set up MCP Toolset pointing to our local server
mcp_server_path = os.path.join(os.path.dirname(__file__), "mcp_server.py")
policy_mcp_toolset = McpToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command=sys.executable,
            args=[mcp_server_path],
        )
    ),
    tool_filter=["check_policy"],
)

# -----------------
# Pydantic Schemas
# -----------------
class LogIndex(BaseModel):
    index: int

class ClassificationResult(BaseModel):
    app_category: str = Field(description="The application category of the log entry.")
    policy_status: str = Field(description="Policy status evaluated by check_policy tool.")
    risk_level: str = Field(description="High Risk or Corporate Approved.")
    explanation: str = Field(description="Explanation of the risk level.")

class AuditResult(BaseModel):
    log_index: int
    user: str
    app_category: str
    proxy_action: str
    file_type: str
    data_sensitivity: str
    classification_status: str
    audit_decision: str = Field(description="Must be 'SECURITY VIOLATION' or 'ALLOW'.")
    reason: str

# -----------------
# Nodes and Agents
# -----------------
def preprocess_index(ctx: Context, node_input: Any) -> Event:
    """Extracts the index integer from raw user input."""
    index = -1
    if isinstance(node_input, dict):
        index = int(node_input.get("index", 0))
    elif hasattr(node_input, "index"):
        index = int(getattr(node_input, "index"))
    elif isinstance(node_input, types.Content):
        # Fallback if raw text
        for part in node_input.parts:
            if part.text:
                import json
                try:
                    data = json.loads(part.text)
                    index = int(data.get("index", 0))
                except Exception:
                    if part.text.strip().isdigit():
                        index = int(part.text.strip())
                break
    
    return Event(output=LogIndex(index=index))

def get_log_entry_node(ctx: Context, node_input: LogIndex) -> Event:
    """Reads the CSV file using the index and stores the entry in the session state."""
    res = get_log_entry(node_input.index)
    if res["status"] == "success":
        entry = res["log_entry"]
        # Save to state so downstream auditor can see it
        ctx.state["log_entry"] = str(entry)
        ctx.state["log_index"] = node_input.index
        return Event(output=f"Log Entry to classify: {entry}")
    return Event(output=f"Error reading log: {res.get('message')}")

classifier_agent = LlmAgent(
    name="classifier",
    model=gemini_model,
    instruction=(
        "You are a Security Log Classifier. "
        "Use the `check_policy` tool to check the policy status of the app_category found in the log entry. "
        "Analyze the risk level of the category and produce a structured ClassificationResult. "
        "Your explanation should summarize the policy status and risk level of the app category. "
        "IMPORTANT: You MUST return ONLY valid JSON matching the ClassificationResult schema. "
        "Do NOT include any markdown formatting (like ```json), backticks, or conversational text. Just the raw JSON object."
    ),
    tools=[policy_mcp_toolset],
    output_schema=ClassificationResult,
    output_key="classification",
)

auditor_agent = LlmAgent(
    name="auditor",
    model=gemini_model,
    instruction=(
        "You are a DLP Auditor. "
        "The current log entry data is: {log_entry}. "
        "The log index is: {log_index}. "
        "You will also receive the ClassificationResult from the classifier agent as your input. "
        "Guardrail: If data_sensitivity is 'Confidential' or 'Critical' AND the app_category is 'Webmail' or 'Personal Storage' or 'Text Sharing', flag the audit_decision as 'SECURITY VIOLATION'. "
        "Otherwise, flag the audit_decision as 'ALLOW'. "
        "Make sure to strictly adhere to the Guardrail and output the AuditResult. Ensure the log_index matches {log_index}. "
        "IMPORTANT: You MUST return ONLY valid JSON matching the AuditResult schema. "
        "Do NOT include any markdown formatting (like ```json), backticks, or conversational text. Just the raw JSON object."
    ),
    output_schema=AuditResult,
    output_key="audit_result",
)

# -----------------
# Workflow Graph
# -----------------
root_agent = Workflow(
    name="dlp_workflow",
    edges=[
        (START, preprocess_index),
        (preprocess_index, get_log_entry_node),
        (get_log_entry_node, classifier_agent),
        (classifier_agent, auditor_agent),
    ],
    output_schema=AuditResult,
)

from google.adk.apps import App
app = App(name="app", root_agent=root_agent)
