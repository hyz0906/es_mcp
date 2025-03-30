import os
import json
from typing import Dict, List, Any, Tuple, Optional, Literal
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from pydantic import BaseModel, Field
import pickle
import socket
from langchain_core.messages import HumanMessage, AIMessage
from langchain.memory import ConversationBufferMemory

# MCP Client for communicating with our Elasticsearch MCP server
class MCPClient:
    def __init__(self, host="localhost", port=8000):
        self.host = host
        self.port = port
        # Get tools list on initialization
        self.tools = self.get_tools()
    
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

    def get_tools(self) -> dict:
        """Get the list of available tools from the MCP server"""
        response = self.send_command("list_tools")
        if response["status"] == "ok":
            return response["data"]["available_tools"]
        else:
            raise Exception(f"Failed to get tools list: {response['message']}")

# Define the state for our agent
class AgentState(BaseModel):
    query: str = Field(description="The user's natural language query")
    thoughts: List[str] = Field(default_factory=list, description="Agent's thoughts during processing")
    mcp_command: Optional[str] = Field(default=None, description="The MCP command to execute")
    mcp_params: Dict[str, Any] = Field(default_factory=dict, description="Parameters for the MCP command")
    response: Optional[Dict[str, Any]] = Field(default=None, description="Response from the MCP server")
    answer: Optional[str] = Field(default=None, description="Final answer to present to the user")
    memory: ConversationBufferMemory = Field(
        default_factory=lambda: ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True
        ),
        description="Conversation memory"
    )
    context: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional context from previous interactions"
    )
    task_list: List[str] = Field(default_factory=list, description="List of tasks to complete")
    current_task: Optional[str] = Field(default=None, description="Current task being executed")
    task_status: str = Field(default="planning", description="Current status of task execution")

# Initialize the LLM
llm = ChatOpenAI(
    model="deepseek-ai/DeepSeek-R1-Distill-Qwen-7B",
    temperature=0,
    base_url="https://api.siliconflow.cn/v1",
    api_key=os.getenv("SILICONFLOW_API_KEY", "sk-xxx")
)

# Initialize MCP client and get tools
mcp_client = MCPClient()

# Create dynamic prompt using available tools
tools_description = ""
for name, tool in mcp_client.tools.items():
    tools_description += f"- {name}: {tool['description']}\n"
    if tool['parameters']:
        tools_description += "  Parameters:\n"
        for param, desc in tool['parameters'].items():
            tools_description += f"    - {param}: {desc}\n"

analyze_query_prompt = ChatPromptTemplate.from_template("""You are an Elasticsearch expert assistant. Your job is to analyze the user's query and determine which Elasticsearch operation to perform.

Available MCP commands:
{tools}

Previous Context:
{context}

Chat History:
{chat_history}

Current Query: {query}

Think step by step about what the user is asking for and which Elasticsearch operation would best satisfy their request.
Consider the chat history and previous context when interpreting the current query.
The user might refer to previous queries, results, or specific indices/documents mentioned before.

Output your thoughts and then determine:
1. The MCP command to execute
2. The parameters needed for that command

Your response should be in JSON format with the following structure:
{{"thoughts": ["thought1", "thought2"], "command": "command_name", "parameters": {{"param1": "value1", "param2": "value2"}}}}
""")

def summarize_search_results(results: dict, max_items: int = 5) -> dict:
    """Summarize search results to prevent token overflow while preserving data"""
    if "hits" not in results.get("data", {}).get("hits", {}):
        return results
    
    original_hits = results["data"]["hits"]["hits"]
    total_hits = len(original_hits)
    
    if total_hits > max_items:
        # Store complete results in context
        results["data"]["complete_results"] = original_hits
        
        # Keep only the first max_items results for immediate display
        results["data"]["hits"]["hits"] = original_hits[:max_items]
        
        # Add summary information
        results["data"]["summary"] = {
            "total_hits": total_hits,
            "shown_hits": max_items,
            "omitted_hits": total_hits - max_items,
            "available_pages": (total_hits + max_items - 1) // max_items,
            "current_page": 1,
            "note": f"Showing first {max_items} of {total_hits} results. You can view more results by asking for the next page."
        }
    
    return results

def get_page_from_results(complete_results: list, page: int, page_size: int = 5) -> list:
    """Get a specific page from complete results"""
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    return complete_results[start_idx:end_idx]

def analyze_query(state: AgentState) -> AgentState:
    """Analyze the user query and determine the appropriate MCP command"""
    chat_history = state.memory.load_memory_variables({})["chat_history"]
    
    # Handle pagination requests
    if state.current_task and any(x in state.current_task.lower() for x in ["next page", "page", "more results"]):
        if "last_search" in state.context:
            current_page = state.context["last_search"].get("current_page", 1)
            state.mcp_command = "page"  # Special command for pagination
            state.mcp_params = {"page": current_page + 1}
            return state
    
    # Normal query analysis
    response = llm.invoke(analyze_query_prompt.format_messages(
        query=state.query,
        tools=tools_description,
        chat_history=chat_history,
        context=json.dumps(state.context, indent=2)
    ))
    result = json.loads(response.content)
    
    state.thoughts.extend(result["thoughts"])
    state.mcp_command = result["command"]
    state.mcp_params = result["parameters"]
    return state

def execute_command(state: AgentState) -> AgentState:
    """Execute the MCP command and store the response"""
    # Check if this is a pagination request
    if state.current_task and "page" in state.current_task.lower():
        if "last_search" in state.context and "complete_results" in state.context["last_search"]:
            page = int(state.mcp_params.get("page", 2))  # Default to page 2 for "next page"
            complete_results = state.context["last_search"]["complete_results"]
            
            # Get the requested page
            page_results = get_page_from_results(complete_results, page)
            
            # Create paginated response
            state.response = {
                "status": "ok",
                "data": {
                    "hits": {
                        "hits": page_results,
                        "total": len(complete_results)
                    },
                    "summary": {
                        "total_hits": len(complete_results),
                        "shown_hits": len(page_results),
                        "current_page": page,
                        "available_pages": (len(complete_results) + 4) // 5,
                        "note": f"Showing page {page} of results"
                    }
                }
            }
            return state
    
    # Normal command execution
    state.response = mcp_client.send_command(state.mcp_command, state.mcp_params)
    
    # Update context based on the command and response
    if state.response["status"] == "ok":
        if state.mcp_command == "indices":
            state.context["last_indices"] = state.response["data"]
        elif state.mcp_command == "search":
            # Summarize search results before storing
            summarized_response = summarize_search_results(state.response)
            
            # Store complete results in context
            if "complete_results" in summarized_response["data"]:
                state.context["last_search"] = {
                    "index": state.mcp_params.get("index"),
                    "query": state.mcp_params.get("query"),
                    "complete_results": summarized_response["data"]["complete_results"],
                    "current_page": 1
                }
            
            # Update response with summarized version
            state.response = summarized_response
            
        elif state.mcp_command == "document":
            state.context["last_document"] = {
                "index": state.mcp_params.get("index"),
                "id": state.mcp_params.get("id"),
                "content": state.response["data"]
            }
    
    return state

format_response_prompt = ChatPromptTemplate.from_template("""
You are an Elasticsearch expert assistant. Format the response from Elasticsearch into a clear, user-friendly answer.

Previous Context:
{context}

Chat History:
{chat_history}

Current Query: {query}
Response: {response}

Please provide a natural, conversational response that answers the user's query.
Consider the chat history and previous context when formulating your response.
You can refer to previous interactions and stored information if relevant.
""")

def format_response(state: AgentState) -> AgentState:
    """Format the response and determine next steps"""
    chat_history = state.memory.load_memory_variables({})["chat_history"]
    
    response = llm.invoke(format_response_prompt.format_messages(
        query=state.query,
        response=json.dumps(state.response),
        chat_history=chat_history,
        context=json.dumps(state.context, indent=2)
    ))
    state.answer = response.content
    
    # Save interaction to memory
    state.memory.save_context(
        {"input": state.query if not state.current_task else f"[{state.current_task}] {state.query}"},
        {"output": state.answer}
    )
    
    # If there are more tasks, continue executing
    if state.task_list:
        state.current_task = state.task_list.pop(0)
        state.task_status = "executing"
    else:
        state.task_status = "need_feedback"
    
    return state

plan_task_prompt = ChatPromptTemplate.from_template("""You are an Elasticsearch expert assistant. Your job is to break down the user's query into a series of steps that can be executed using the available commands.

Available MCP commands:
{tools}

Previous Context:
{context}

Chat History:
{chat_history}

Current Query: {query}

Think step by step about what tasks need to be done to fulfill this request.
If the request can be done in one step, just plan that step.
If it requires multiple steps, break it down into sequential tasks.

Output your plan in JSON format:
{{
    "thoughts": ["thought1", "thought2"],
    "tasks": ["task1", "task2"],  // List of tasks in order
    "single_step": true/false     // Whether this can be done in one step
}}
""")

def plan_task(state: AgentState) -> AgentState:
    """Plan the tasks needed to fulfill the request"""
    chat_history = state.memory.load_memory_variables({})["chat_history"]
    
    response = llm.invoke(plan_task_prompt.format_messages(
        query=state.query,
        tools=tools_description,
        chat_history=chat_history,
        context=json.dumps(state.context, indent=2)
    ))
    result = json.loads(response.content)
    
    state.thoughts.extend(result["thoughts"])
    state.task_list = result["tasks"]
    state.task_status = "executing" if result["tasks"] else "done"
    
    if state.task_list:
        state.current_task = state.task_list.pop(0)
    
    return state

def route(state: AgentState) -> Literal["analyze", "plan", "execute", "format", "human_feedback", END]:
    """Route the workflow based on current state"""
    if state.task_status == "planning":
        return "plan"
    elif state.task_status == "executing":
        return "analyze"
    elif state.task_status == "need_feedback":
        return "human_feedback"
    elif state.task_status == "continue":
        return "plan"
    else:
        return END

def get_human_feedback(state: AgentState) -> AgentState:
    """Get feedback from human on whether the result is satisfactory"""
    print("\nIs this result satisfactory? (yes/no):")
    feedback = input().strip().lower()
    
    if feedback == "yes":
        state.task_status = "done"
    else:
        print("\nWhat would you like to know more about?")
        state.query = input().strip()
        state.task_status = "continue"
    
    return state

# Create the workflow
workflow = StateGraph(AgentState)

# Add nodes
workflow.add_node("plan", plan_task)
workflow.add_node("analyze", analyze_query)
workflow.add_node("execute", execute_command)
workflow.add_node("format", format_response)
workflow.add_node("human_feedback", get_human_feedback)

# Add edges
workflow.add_edge("plan", "analyze")
workflow.add_edge("analyze", "execute")
workflow.add_edge("execute", "format")
workflow.add_edge("format", route)
workflow.add_edge("human_feedback", route)

# Set entry point
workflow.set_entry_point("plan")

# Compile the workflow
app = workflow.compile()

def interactive_session():
    """Run an interactive session with the Elasticsearch agent"""
    print("Elasticsearch Agent: Hello! I can help you interact with Elasticsearch. Type 'exit' to end the session.")
    
    # Initialize state
    state = AgentState(query="")
    
    while True:
        if not state.query:  # Only ask for input if we don't have a query
            query = input("\nYou: ").strip()
            
            if query.lower() in ['exit', 'quit', 'bye']:
                print("\nElasticsearch Agent: Goodbye!")
                break
            
            state.query = query
            state.task_status = "planning"
        
        # Process query
        result = app.invoke(state)
        
        # Update state
        state = result
        
        # Print response
        if state.answer:
            print(f"\nElasticsearch Agent: {state.answer}")
            
            if state.current_task:
                print(f"\nCurrent task: {state.current_task}")

if __name__ == "__main__":
<<<<<<< HEAD
    # Example usage
    query = "What indices are available in Elasticsearch?"
    response = process_query(query)
    print(response)
=======
    interactive_session()
>>>>>>> c7a733a (get tools and  multi step with human in loop)
