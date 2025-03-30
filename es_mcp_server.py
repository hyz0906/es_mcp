from fastmcp import FastMCP
from elasticsearch import Elasticsearch
import os

class ElasticsearchTool:
    """Tool for interacting with Elasticsearch"""
    
    def __init__(self):
        self.es_client = Elasticsearch(
            os.environ.get('ELASTICSEARCH_URL', 'https://localhost:9200'),
            basic_auth=(
                os.environ.get('ELASTICSEARCH_USERNAME', 'elastic'),
                os.environ.get('ELASTICSEARCH_PASSWORD', '123456')
            )
        )

    def health(self) -> dict:
        """Get Elasticsearch cluster health"""
        try:
            health = self.es_client.cluster.health()
            return {"status": "ok", "data": {"elasticsearch": health}}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def indices(self) -> dict:
        """List all indices in Elasticsearch"""
        try:
            indices = self.es_client.cat.indices(format="json")
            return {"status": "ok", "data": indices}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def search(self, index: str, query: dict = None, size: int = 100, 
               from_param: int = 0, sort: dict = None) -> dict:
        """Search logs in Elasticsearch"""
        try:
            if not index:
                return {"status": "error", "message": "Index name is required"}
            
            search_params = {
                "index": index,
                "size": size,
                "from_": from_param,
                "body": {}
            }
            
            if query:
                search_params["body"]["query"] = query
            
            if sort:
                search_params["body"]["sort"] = sort
            
            result = self.es_client.search(**search_params)
            return {"status": "ok", "data": result}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def document(self, index: str, doc_id: str) -> dict:
        """Get document by ID"""
        try:
            if not index or not doc_id:
                return {"status": "error", "message": "Both index and id are required"}
            
            result = self.es_client.get(index=index, id=doc_id)
            return {"status": "ok", "data": result}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def mapping(self, index: str) -> dict:
        """Get index mapping"""
        try:
            if not index:
                return {"status": "error", "message": "Index name is required"}
            
            result = self.es_client.indices.get_mapping(index=index)
            return {"status": "ok", "data": result}
        except Exception as e:
            return {"status": "error", "message": str(e)}

class ElasticsearchMCP(FastMCP):
    def __init__(self):
        super().__init__()
        self.es_tool = ElasticsearchTool()
        self.tools = {}  # Initialize empty tools dictionary
        
        # Register all tools
        self.register_tool(
            "health",
            "Check Elasticsearch cluster health",
            {},
            self.es_tool.health
        )
        
        self.register_tool(
            "indices",
            "List all indices in Elasticsearch",
            {},
            self.es_tool.indices
        )
        
        self.register_tool(
            "search",
            "Search for documents in an index",
            {
                "index": "Name of the index to search",
                "query": "Search query in Elasticsearch DSL format",
                "size": "Number of results to return (default: 100)",
                "from": "Starting offset for pagination",
                "sort": "Sort criteria"
            },
            lambda params: self.es_tool.search(
                index=params.get('index'),
                query=params.get('query'),
                size=params.get('size', 100),
                from_param=params.get('from', 0),
                sort=params.get('sort')
            )
        )
        
        self.register_tool(
            "document",
            "Get a specific document by ID",
            {
                "index": "Name of the index",
                "id": "Document ID"
            },
            lambda params: self.es_tool.document(
                index=params.get('index'),
                doc_id=params.get('id')
            )
        )
        
        self.register_tool(
            "mapping",
            "Get the mapping for an index",
            {
                "index": "Name of the index"
            },
            lambda params: self.es_tool.mapping(
                index=params.get('index')
            )
        )
        
        # Register the list_tools command
        self.register_tool(
            "list_tools",
            "Get list of available tools and their descriptions",
            {},
            lambda _: {"available_tools": self.tools}
        )

    def register_tool(self, name: str, description: str, parameters: dict, handler: callable):
        """Register a new tool with the MCP server"""
        self.tools[name] = {
            "description": description,
            "parameters": parameters,
            "handler": handler
        }

    def handle_request(self, command: str, params: dict) -> dict:
        """Handle incoming MCP requests"""
        tool = self.tools.get(command)
        if tool:
            try:
                result = tool["handler"](params)
                return {"status": "ok", "data": result}
            except Exception as e:
                return {"status": "error", "message": str(e)}
        else:
            return {
                "status": "error", 
                "message": f"Unknown command: {command}",
                "available_tools": list(self.tools.keys())
            }

def main():
    # Get port from environment or use default
    port = int(os.environ.get('PORT', 8000))
    
    # Create and start the MCP server
    server = ElasticsearchMCP()
    
    print(f"Elasticsearch MCP server starting on port {port}")
    server.run()

if __name__ == "__main__":
    main()