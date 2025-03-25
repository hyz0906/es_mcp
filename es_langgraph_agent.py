import os
import json
from typing import Dict, List, Any, Tuple, Optional
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from pydantic import BaseModel, Field
import pickle
import socket

# MCP Client for communicating with our Elasticsearch MCP server
class MCPClient:
    def __init__(self, host, port):
        self.host = host
        self.port = port
    
    def send_command(self, command, params=None):
        """Send a command to the MCP server and return the response"""
        if params is None:
            params = {}
        
        # Create request
        request = {
            'command': command,
            'params': params
        }
        
        # Create socket
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        
        try:
            # Connect to server
            client_socket.connect((self.host, self.port))
            
            # Send request
            client_socket.sendall(pickle.dumps(request))
            
            # Receive response
            data = b''
            while True:
                chunk = client_socket.recv(4096)
                if not chunk:
                    break
                data += chunk
                
                # Try to unpickle the data to see if it's complete
                try:
                    response = pickle.loads(data)
                    break
                except:
                    # Not complete yet, continue receiving
                    continue
            
            return response
        except Exception as e:
            return {"status": "error", "message": f"Client error: {str(e)}"}
        finally:
            client_socket.close()

# Define the state for our agent
class AgentState(BaseModel):
    query: str = Field(description="The user's natural language query")
    thoughts: List[str] = Field(default_factory=list, description="Agent's thoughts during processing")
    mcp_command: Optional[str] = Field(default=None, description="The MCP command to execute")
    mcp_params: Dict[str, Any] = Field(default_factory=dict, description="Parameters for the MCP command")
    response: Optional[Dict[str, Any]] = Field(default=None, description="Response from the MCP server")
    answer: Optional[str] = Field(default=None, description="Final answer to present to the user")

# Initialize the LLM
llm = ChatOpenAI(
    model="deepseek-ai/DeepSeek-R1-Distill-Qwen-7B",
    temperature=0,
    base_url="https://api.siliconflow.cn/v1",
    api_key=os.getenv("SILICONFLOW_API_KEY", "sk-xxx")
)

# Initialize the MCP client
mcp_client = MCPClient("localhost", 8000)

# Define the prompts
analyze_query_prompt = ChatPromptTemplate.from_template("""You are an Elasticsearch expert assistant. Your job is to analyze the user's query and determine which Elasticsearch operation to perform.

Available MCP commands:
- health: Check Elasticsearch cluster health
- indices: List all indices in Elasticsearch
- search: Search for documents in an index
- document: Get a specific document by ID
- mapping: Get the mapping for an index

User query: {query}

Think step by step about what the user is asking for and which Elasticsearch operation would best satisfy their request.

Output your thoughts and then determine:
1. The MCP command to execute
2. The parameters needed for that command

Your response should be in JSON format with the following structure:
{{"thoughts": ["thought1", "thought2"], "command": "command_name", "parameters": {{"param1": "value1", "param2": "value2"}}}}
""")

# Define the agent functions
def analyze_query(state: AgentState) -> AgentState:
    """Analyze the user query and determine the appropriate MCP command"""
    response = llm.invoke(analyze_query_prompt.format_messages(query=state.query))
    result = json.loads(response.content)
    
    state.thoughts.extend(result["thoughts"])
    state.mcp_command = result["command"]
    state.mcp_params = result["parameters"]
    return state

def execute_command(state: AgentState) -> AgentState:
    """Execute the MCP command and store the response"""
    state.response = mcp_client.send_command(state.mcp_command, state.mcp_params)
    return state

format_response_prompt = ChatPromptTemplate.from_template("""
You are an Elasticsearch expert assistant. Format the response from Elasticsearch into a clear, user-friendly answer.

Query: {query}
Response: {response}

Please provide a natural, conversational response that answers the user's query.
""")

def format_response(state: AgentState) -> AgentState:
    """Format the response into a user-friendly answer"""
    response = llm.invoke(format_response_prompt.format_messages(
        query=state.query,
        response=json.dumps(state.response)
    ))
    state.answer = response.content
    return state

# Create the workflow
workflow = StateGraph(AgentState)

# Add nodes
workflow.add_node("analyze", analyze_query)
workflow.add_node("execute", execute_command)
workflow.add_node("format", format_response)

# Add edges
workflow.add_edge("analyze", "execute")
workflow.add_edge("execute", "format")
workflow.add_edge("format", END)

# Set entry point
workflow.set_entry_point("analyze")

# Compile the workflow
app = workflow.compile()

def process_query(query: str) -> str:
    """Process a user query and return the response"""
    state = AgentState(query=query)
    result = app.invoke(state)
    # The result is a dict-like object, we need to access it like a dictionary
    return result["answer"]

if __name__ == "__main__":
    # Example usage
    query = "What indices are available in Elasticsearch?"
    response = process_query(query)
    print(response)
