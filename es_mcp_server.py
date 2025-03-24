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

    def handle_request(self, command: str, params: dict) -> dict:
        """Handle incoming MCP requests"""
        handlers = {
            "health": lambda: self.es_tool.health(),
            "indices": lambda: self.es_tool.indices(),
            "search": lambda: self.es_tool.search(
                index=params.get('index'),
                query=params.get('query'),
                size=params.get('size', 100),
                from_param=params.get('from', 0),
                sort=params.get('sort')
            ),
            "document": lambda: self.es_tool.document(
                index=params.get('index'),
                doc_id=params.get('id')
            ),
            "mapping": lambda: self.es_tool.mapping(
                index=params.get('index')
            )
        }

        handler = handlers.get(command)
        if handler:
            return handler()
        else:
            return {"status": "error", "message": f"Unknown command: {command}"}

def main():
    # Get port from environment or use default
    port = int(os.environ.get('PORT', 8000))
    
    # Create and start the MCP server
    server = ElasticsearchMCP()
    
    print(f"Elasticsearch MCP server starting on port {port}")
    server.run()

if __name__ == "__main__":
    main()