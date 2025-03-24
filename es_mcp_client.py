import socket
import pickle
import json

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

def print_response(response):
    """Pretty print the MCP response"""
    print(f"Status: {response.get('status')}")
    if response.get('message'):
        print(f"Message: {response.get('message')}")
    if response.get('data'):
        print("Data:")
        print(json.dumps(response.get('data'), indent=2))
    print("-" * 50)

def main():
    # Connect to the MCP server
    client = MCPClient("localhost", 8000)
    
    # Check health
    print("Checking Elasticsearch health...")
    response = client.send_command("health")
    print_response(response)
    
    # List indices
    print("Listing indices...")
    response = client.send_command("indices")
    print_response(response)
    
    # Search logs
    print("Searching logs...")
    search_params = {
        "index": "logs-*",
        "query": {
            "match_all": {}
        },
        "size": 5
    }
    response = client.send_command("search", search_params)
    print_response(response)
    
    # Get document by ID (replace with actual index and ID)
    print("Getting document...")
    doc_params = {
        "index": "your-index",
        "id": "your-document-id"
    }
    response = client.send_command("document", doc_params)
    print_response(response)
    
    # Get index mapping
    print("Getting index mapping...")
    mapping_params = {
        "index": "your-index"
    }
    response = client.send_command("mapping", mapping_params)
    print_response(response)

if __name__ == "__main__":
    main() 