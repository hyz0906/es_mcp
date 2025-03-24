# Elasticsearch MCP Server (Python)

A Management Control Protocol (MCP) server for querying Elasticsearch indices and logs, implemented in Python using the MCP package.

## Setup

1. Create a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Configure environment variables:
   ```
   export ELASTICSEARCH_URL=http://your-elasticsearch-host:9200
   export ELASTICSEARCH_USERNAME=your-username
   export ELASTICSEARCH_PASSWORD=your-password
   export PORT=8000
   ```
   On Windows:
   ```
   set ELASTICSEARCH_URL=http://your-elasticsearch-host:9200
   set ELASTICSEARCH_USERNAME=your-username
   set ELASTICSEARCH_PASSWORD=your-password
   set PORT=8000
   ```

4. Start the server:
   ```
   python es_mcp_server.py
   ```

## MCP Commands

The server supports the following MCP commands:

### Health Check
```
Command: health
Params: {}
```

### List Indices
```
Command: indices
Params: {}
```

### Search Logs
```
Command: search
Params: {
  "index": "your-index-name",
  "query": {
    "match": {
      "message": "error"
    }
  },
  "size": 100,
  "from": 0,
  "sort": [
    { "@timestamp": "desc" }
  ]
}
```

### Get Document by ID
```
Command: document
Params: {
  "index": "your-index",
  "id": "document-id"
}
```

### Get Index Mapping
```
Command: mapping
Params: {
  "index": "your-index"
}
```

## Example Client Usage

A sample client script is provided in `es_mcp_client.py`. You can run it to test the MCP server:

```
python es_mcp_client.py
```

You can also use the MCP client in your own Python code:

```python
from mcp import MCPClient

client = MCPClient("localhost", 8000)
response = client.send_command("health")
print(response.status)
print(response.data)

# Search for logs
search_params = {
    "index": "logs-*",
    "query": {
        "bool": {
            "must": [
                { "match": { "level": "error" } }
            ],
            "filter": [
                { "range": { "@timestamp": { "gte": "now-24h" } } }
            ]
        }
    },
    "size": 50,
    "sort": [{ "@timestamp": "desc" }]
}
response = client.send_command("search", search_params)
```

## Notes

- The MCP server uses a binary protocol for efficient communication
- Multiple clients can connect to the server simultaneously
- The server handles commands asynchronously 