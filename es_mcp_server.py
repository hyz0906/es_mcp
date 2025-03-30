import socket
import pickle
import os
from elasticsearch import Elasticsearch
from typing import Dict, Any
import threading

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

class MCPServer:
    def __init__(self, host="0.0.0.0", port=8000):
        self.host = host
        self.port = port
        self.es_tool = ElasticsearchTool()
        self.tools = self.register_tools()
        self.server_socket = None

    def register_tools(self) -> Dict[str, Dict[str, Any]]:
        """Register all available tools"""
        return {
            "health": {
                "description": "Check Elasticsearch cluster health",
                "parameters": {},
                "handler": self.es_tool.health
            },
            "indices": {
                "description": "List all indices in Elasticsearch",
                "parameters": {},
                "handler": self.es_tool.indices
            },
            "search": {
                "description": "Search for documents in an index",
                "parameters": {
                    "index": "Name of the index to search",
                    "query": "Search query in Elasticsearch DSL format",
                    "size": "Number of results to return (default: 100)",
                    "from": "Starting offset for pagination",
                    "sort": "Sort criteria"
                },
                "handler": self.es_tool.search
            },
            "document": {
                "description": "Get a specific document by ID",
                "parameters": {
                    "index": "Name of the index",
                    "id": "Document ID"
                },
                "handler": self.es_tool.document
            },
            "mapping": {
                "description": "Get the mapping for an index",
                "parameters": {
                    "index": "Name of the index"
                },
                "handler": self.es_tool.mapping
            },
            "list_tools": {
                "description": "Get list of available tools and their descriptions",
                "parameters": {},
                "handler": lambda: {"available_tools": {
                    name: {k: v for k, v in info.items() if k != 'handler'}
                    for name, info in self.tools.items()
                }}
            }
        }

    def handle_client(self, client_socket: socket.socket, address: tuple):
        """Handle individual client connection"""
        try:
            # Receive data
            data = b''
            while True:
                chunk = client_socket.recv(4096)
                if not chunk:
                    break
                data += chunk
                try:
                    request = pickle.loads(data)
                    break
                except:
                    continue

            # Process request
            command = request.get('command')
            params = request.get('params', {})
            
            tool = self.tools.get(command)
            if tool:
                try:
                    result = tool["handler"](**params)
                    response = {"status": "ok", "data": result}
                except Exception as e:
                    response = {"status": "error", "message": str(e)}
            else:
                response = {
                    "status": "error",
                    "message": f"Unknown command: {command}",
                    "available_tools": list(self.tools.keys())
                }

            # Send response
            client_socket.sendall(pickle.dumps(response))

        except Exception as e:
            error_response = {"status": "error", "message": f"Server error: {str(e)}"}
            try:
                client_socket.sendall(pickle.dumps(error_response))
            except:
                pass
        finally:
            client_socket.close()

    def run(self):
        """Start the MCP server"""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            print(f"MCP Server listening on {self.host}:{self.port}")
            
            while True:
                client_socket, address = self.server_socket.accept()
                print(f"Accepted connection from {address}")
                
                # Handle each client in a separate thread
                client_thread = threading.Thread(
                    target=self.handle_client,
                    args=(client_socket, address)
                )
                client_thread.start()
                
        except KeyboardInterrupt:
            print("\nShutting down server...")
        finally:
            if self.server_socket:
                self.server_socket.close()

def main():
    # Get port from environment or use default
    port = int(os.environ.get('PORT', 8000))
    
    # Create and start the MCP server
    server = MCPServer(port=port)
    server.run()

if __name__ == "__main__":
    main()