import os
import json
import mcp
import socket
import threading
import pickle
from elasticsearch import Elasticsearch

# Let's try to find the correct handler class
# Uncomment one of these approaches based on what's available in your mcp package
# Option 1: If Handler is in a submodule
# from mcp.handler import Handler

# Option 2: If it has a different name
# class ElasticsearchMCPHandler(mcp.MCPHandler):

# Option 3: Create our own handler class that works with mcp
class ElasticsearchMCPHandler:
    def __init__(self):
        # Initialize Elasticsearch client
        self.es_client = Elasticsearch(
            os.environ.get('ELASTICSEARCH_URL', 'https://localhost:9200'),
            basic_auth=(
                os.environ.get('ELASTICSEARCH_USERNAME', 'elastic'),
                os.environ.get('ELASTICSEARCH_PASSWORD', '123456')
            )
        )
        
        # Command handlers dictionary
        self.handlers = {
            "health": self.handle_health,
            "indices": self.handle_indices,
            "search": self.handle_search,
            "document": self.handle_document,
            "mapping": self.handle_mapping
        }
    
    def handle_command(self, command, params):
        """Route commands to the appropriate handler"""
        if command in self.handlers:
            return self.handlers[command](params)
        else:
            return {"status": "error", "message": f"Unknown command: {command}"}
    
    def handle_health(self, params):
        """Get Elasticsearch cluster health"""
        try:
            health = self.es_client.cluster.health()
            return {"status": "ok", "data": {"elasticsearch": health}}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def handle_indices(self, params):
        """List all indices in Elasticsearch"""
        try:
            indices = self.es_client.cat.indices(format="json")
            return {"status": "ok", "data": indices}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def handle_search(self, params):
        """Search logs in Elasticsearch"""
        try:
            index = params.get('index')
            query = params.get('query')
            size = params.get('size', 100)
            from_param = params.get('from', 0)
            sort = params.get('sort')
            
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
    
    def handle_document(self, params):
        """Get document by ID"""
        try:
            index = params.get('index')
            doc_id = params.get('id')
            
            if not index or not doc_id:
                return {"status": "error", "message": "Both index and id are required"}
            
            result = self.es_client.get(index=index, id=doc_id)
            return {"status": "ok", "data": result}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def handle_mapping(self, params):
        """Get index mapping"""
        try:
            index = params.get('index')
            
            if not index:
                return {"status": "error", "message": "Index name is required"}
            
            result = self.es_client.indices.get_mapping(index=index)
            return {"status": "ok", "data": result}
        except Exception as e:
            return {"status": "error", "message": str(e)}

# Simple MCP server implementation
class MCPServer:
    def __init__(self, handler, host='0.0.0.0', port=8000):
        self.handler = handler
        self.host = host
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
    def handle_client(self, client_socket):
        """Handle client connection"""
        try:
            # Receive data from client
            data = b''
            while True:
                chunk = client_socket.recv(4096)
                if not chunk:
                    break
                data += chunk
                
                # Try to unpickle the data to see if it's complete
                try:
                    request = pickle.loads(data)
                    break
                except:
                    # Not complete yet, continue receiving
                    continue
            
            if not data:
                return
                
            # Process the command
            command = request.get('command')
            params = request.get('params', {})
            
            # Handle the command
            response = self.handler.handle_command(command, params)
            
            # Send response back to client
            client_socket.sendall(pickle.dumps(response))
        except Exception as e:
            print(f"Error handling client: {e}")
        finally:
            client_socket.close()
    
    def start(self):
        """Start the MCP server"""
        self.socket.bind((self.host, self.port))
        self.socket.listen(5)
        print(f"MCP server listening on {self.host}:{self.port}")
        
        try:
            while True:
                client_socket, addr = self.socket.accept()
                print(f"Accepted connection from {addr[0]}:{addr[1]}")
                
                # Handle client in a new thread
                client_thread = threading.Thread(
                    target=self.handle_client,
                    args=(client_socket,)
                )
                client_thread.daemon = True
                client_thread.start()
        except KeyboardInterrupt:
            print("Server shutting down...")
        finally:
            self.socket.close()

def main():
    # Get port from environment or use default
    port = int(os.environ.get('PORT', 8000))
    
    # Create and start the MCP server
    handler = ElasticsearchMCPHandler()
    server = MCPServer(handler, port=port)
    
    print(f"Elasticsearch MCP server starting on port {port}")
    server.start()

if __name__ == "__main__":
    main() 