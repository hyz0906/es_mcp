# Elasticsearch Query System with LangGraph Agent

A system for interacting with Elasticsearch using natural language queries, consisting of an MCP (Message Control Protocol) server and an intelligent LangGraph agent.

## Introduction

### MCP Server Overview
The MCP Server (`es_mcp_server.py`) is a robust, socket-based interface that handles direct communication with Elasticsearch. It provides:

- **JSON-RPC Protocol**: Implements JSON-RPC 2.0 specification for structured communication
- **Standardized Command Interface**: Offers a consistent API for Elasticsearch operations through a simple command structure
- **Concurrent Processing**: Handles multiple client connections simultaneously using a thread-per-client model
- **Error Handling**: Gracefully manages Elasticsearch connection issues and invalid queries
- **Tool-based Architecture**: Implements a modular tool system for various Elasticsearch operations
- **Security**: Supports authentication and secure communication with Elasticsearch clusters

Key Features:
- JSON-RPC 2.0 compliant request/response handling
- Health checks and cluster monitoring
- Index management and document operations
- Advanced search capabilities with pagination
- Mapping and schema inspection
- Built-in logging and debugging support

Protocol Details:
- **Request Format**:
  ```json
  {
    "jsonrpc": "2.0",
    "method": "command_name",
    "params": {
      "param1": "value1",
      "param2": "value2"
    },
    "id": "request_id"
  }
  ```
- **Response Format**:
  ```json
  {
    "jsonrpc": "2.0",
    "result": {
      "data": "response_data"
    },
    "id": "request_id"
  }
  ```
- **Error Format**:
  ```json
  {
    "jsonrpc": "2.0",
    "error": {
      "code": -32601,
      "message": "Method not found"
    },
    "id": "request_id"
  }
  ```

### LangGraph Agent Overview
The LangGraph Agent (`es_langgraph_agent.py`) is an intelligent interface that processes natural language queries and manages complex interactions with Elasticsearch. It features:

- **Natural Language Processing**: Understands and interprets user queries in plain English
- **Stateful Workflow**: Maintains context and conversation history for follow-up questions
- **Autonomous Operation**: Automatically evaluates and improves results until satisfactory
- **Multi-step Processing**: Breaks down complex queries into manageable steps
- **Visual Workflow**: Provides graphical representation of the processing pipeline

Key Capabilities:
- Automatic query planning and execution
- Context-aware follow-up handling
- Result quality evaluation and improvement
- Pagination and large result set management
- Interactive debugging and visualization

## Components

### 1. MCP Server (es_mcp_server.py)
Handles direct communication with Elasticsearch and provides a standardized interface for operations.

### 2. LangGraph Agent (es_langgraph_agent.py)
Processes natural language queries and manages multi-step interactions with Elasticsearch.

## Setup

1. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install elasticsearch langchain-core langchain-openai langgraph pydantic
   ```

3. Configure environment variables:
   ```bash
   # Elasticsearch Configuration
   export ELASTICSEARCH_URL=http://your-elasticsearch-host:9200
   export ELASTICSEARCH_USERNAME=your-username
   export ELASTICSEARCH_PASSWORD=your-password
   
   # LangGraph Agent Configuration
   export SILICONFLOW_API_KEY=your-api-key
   
   # Server Configuration
   export PORT=8000
   ```

4. Start the MCP server:
   ```bash
   python es_mcp_server.py
   ```

5. In a separate terminal, start the LangGraph agent:
   ```bash
   python es_langgraph_agent.py
   ```

## MCP Server Commands

The server provides the following tools:

### Health Check
```python
{
    "command": "health",
    "params": {}
}
```

### List Indices
```python
{
    "command": "indices",
    "params": {}
}
```

### Search Documents
```python
{
    "command": "search",
    "params": {
        "index": "your-index-name",
        "query": {"match_phrase": {"message": "error"}},
        "size": 100,
        "from": 0,
        "sort": [{"@timestamp": "desc"}]
    }
}
```

### Get Document
```python
{
    "command": "document",
    "params": {
        "index": "your-index",
        "id": "document-id"
    }
}
```

### Get Mapping
```python
{
    "command": "mapping",
    "params": {
        "index": "your-index"
    }
}
```

### List Available Tools
```python
{
    "command": "list_tools",
    "params": {}
}
```

## LangGraph Agent Features

### Natural Language Queries
The agent supports natural language queries like:
- "Show me all indices"
- "Search for error logs from the last hour"
- "Find logs containing 'connection refused'"
- "Get the mapping for index 'logs-2024.03'"

### Multi-step Query Processing
- Automatically breaks down complex queries into steps
- Maintains context between steps
- Shows progress and intermediate results

### Result Management
- Handles large result sets through pagination
- Preserves complete result data
- Supports "show more" and pagination requests

### Context Awareness
- Maintains conversation history
- Understands references to previous queries
- Tracks search context for follow-up questions

## Example Usage

### Using the LangGraph Agent
```bash
$ python es_langgraph_agent.py

Elasticsearch Agent: Hello! How can I help you?

You: Find all error logs from today
Agent: I'll search for error logs. Let me break this down:
1. First, searching for logs with error level...
[Shows results]

You: Show me more details about the first error
Agent: I'll get more information about that specific error...
[Shows detailed information]
```

### Direct MCP Server Usage
```python
import socket
import pickle

def send_command(command, params=None):
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        client_socket.connect(('localhost', 8000))
        request = {'command': command, 'params': params or {}}
        client_socket.sendall(pickle.dumps(request))
        response = pickle.loads(client_socket.recv(4096))
        return response
    finally:
        client_socket.close()

# Example usage
response = send_command('health')
print(response)
```

## Architecture

### MCP Server
- Socket-based communication
- Thread-per-client model
- Tool-based command structure
- Built-in error handling
- Concurrent client support

### LangGraph Agent
- State-based workflow
- Conversation memory management
- Dynamic response formatting
- Pagination handling
- Context preservation

## Error Handling
- Connection errors are gracefully handled
- Invalid queries receive helpful error messages
- Large result sets are managed automatically
- Network timeouts are handled appropriately

## Notes
- The MCP server uses pickle for serialization
- Multiple clients can connect simultaneously
- The LangGraph agent maintains conversation state
- Large result sets are automatically paginated
- All operations are logged for debugging

## License
MIT License 