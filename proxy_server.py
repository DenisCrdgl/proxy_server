import threading
import socket
import time
from urllib.parse import urlparse

# lists
cache = {}
ban_list = set()
c_lock = threading.Lock()
b_lock = threading.Lock()

# constants
PORT = 8080
BUFF_SIZE = 4096
CACHE_TIME = 60

""" 
Summary: Takes in a request from a host, processes the request, and calls the coresponding http handler to process the request

Description: By taking in the client's socket and clients address/path the request is received, decoded,
split into the necessary parts and input into a http handler function depending on the request type. The function
also makes sure that the client socket is properly closed before any instance of return 
(apart from when an excpetion occurs in the try/except section)
"""
def client_handler(cl_sock, cl_add):
    try:
        req = cl_sock.recv(BUFF_SIZE)
        if not req:
            cl_sock.close()
            return
        msg_info = req.split(b'\n')[0]
        method, url, _ = msg_info.decode().split()
        # print(f"Request from {cl_add} from {url} using {method}")
        
        if method == "CONNECT":
            https_handler(cl_sock, url)
        else:
            http_req_handler(cl_sock, req, url)
    except Exception as e:
        print(f"Client handling error: {e}")
    finally:
        cl_sock.close()

""" 
Summary: It takes in a client socket, request sent by the client (other than CONNECT) and the client URL
and processes the request to send an appropriate response back. Uses a caching system + times the response
(in seconds) 

Description: The function parses the input URL into host, port and address/path. It then checks if the host is blocked 
(via the blocked function) and sends a FORBIDDEN response back if host is blocked, otherwise the code continues. The URL
is then checked to see if it is in the cache and withdraws a response from the cache if it finds an entry to send back to
the client, remarking the time it took to do so. If an entry is not marked in the cache the code proceeds to establish a
server socket connection (using hostname + port), retrieves and decodes the request, separating it into the
crucial parts and storing it (encoded) in a variable. This is then sent to the client via the socket connection established
earlier. The response is then initialized as a byte buffer and appended with the info received from the server (given the constant
BUFF_SIZE) which is then stored in the response variable and sent via the client socket. The response + timing for the response is
then cached and closing the server socket. There is an excpetion handler at the end in case there are any problems within the
try section
"""
def http_req_handler(cl_sock, req, url):
    
    parsed_url = urlparse(url)
    host = parsed_url.hostname or url
    port = parsed_url.port or 80
    address = parsed_url.path or "/"
            
    with b_lock:
        if blocked(host):
            print(f"Blocked {url}")
            cl_sock.send(b"HTTP/1.1 403 Forbidden\r\n\r\n")
            return
    
    # strt_time = time.time()
    
    with c_lock:
        if url in cache and time.time() - cache[url][1] < CACHE_TIME:
            response = cache[url][0]
            print(f"{url} found in cache")
            cl_sock.send(response)
            # print(f"Time: {time.time() - strt_time:.3f} seconds")
            return
    
    # print(f"{url} not found in cache")
    
    try:
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.connect((host, port))
        
        request = req.decode().split('\r\n')
        method, _, version = request[0].split()
        request[0] = f"{method} {address} {version}"
        request = "\r\n".join(request).encode()
        
        server_sock.send(request)
        
        response = b""
        while True:
            info = server_sock.recv(BUFF_SIZE)
            if not info:
                break
            response += info
            cl_sock.send(info)
            
        with c_lock:
            cache[url] = (response, time.time())
            
        # print(f"Operation took {time.time() - strt_time:3f} seconds to complete")
        
        server_sock.close()
        
    except Exception as e:
        print(f"HTTP handler error {e}")
        cl_sock.send(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")

"""
Summary: Takes in a client socket + URL and processes a "CONNECTION" request

Description: The code retrieves the hostname and port from the URL and checks if the host is blocked using the blocked function
and sends the client a response if it is blocked, otherwise the code proceedes as usual. The code then opens a socket with the
host and sends a confirmation response to the client via the client socket. A bidirectional connection is then set between server
and host using the send function defined. The code has an exception handler at the end to manage any exceptions within the try section 
"""        
def https_handler(cl_sock, url):
    try:
        
        host, port = url.split(":")
        
        with b_lock:
            if blocked(host):
                # print(f"Blocked {host}")
                cl_sock.send(b"HTTP/1.1 403 Forbidden\r\n\r\n")
                return
            
        # print(f"Connecting to {host}:{port}")
        sock = socket.create_connection((host, port))
        cl_sock.send(b"HTTP/1.1 200 Connection Established\r\n\r\n")
        
        threading.Thread(target=send, args=(cl_sock, sock)).start()
        send(sock, cl_sock)
        
    except Exception as e:
        print(f"Unable to connect {e}")
        cl_sock.send(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
  
"""
Summary: This function initializes the main proxy server

Description: This function sets up the proxy server and binds it to a port. It then calls the server_options function
to allow user input commands (for blocking and unblocking) and sets up an infinite loop for calling threads of the client_handler
using any client socket and address received by the server socket.
"""    
def server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('0.0.0.0', PORT))
    server.listen(100)
    print(f"Proxy server listening on port {PORT}...")
    
    threading.Thread(target=server_options, daemon=True).start()
    
    while True:
        cl_sock, cl_add = server.accept()
        thread = threading.Thread(target=client_handler, args = (cl_sock, cl_add), daemon=True)
        thread.start()

""" 
Summary: Checks the block status of a host

Description: Checks host name in ban list and makes sure that it and any other host linked
with hostname and returns a boolean value if it is in the ban list or not
"""
def blocked(host):
    host = host.lower()
    return any(host == banned or host.endswith("." + banned) for banned in ban_list)
  
"""
Summary: Establishes a connection between sender and receiver

Description: The code receives info from the sender socket and sends it to the receiver socket in an infinite loop (until
there is no more info detected). Just before the termination of the function the sender and receiver are closed appropriately
"""   
def send(sender, receiver):
    try:
        while True:
            info = sender.recv(BUFF_SIZE)
            if not info:
                break
            receiver.send(info)
    except:
        pass
    finally:
        sender.close()
        receiver.close()

"""
Summary: A function that enables users to use the block/unblock commands via the terminal inputs

Description: The terminal input is processed into option (which would be "block" and "unblock") and a target
URL (without the http or https part to make it easier to type in). A match case statement then takes in the inputs
and (depending on what the user wrote) adds/removes the given URL from the ban list. Any other input is ignored or caught by
the null case at the end of the match case section
"""   
def server_options():
    while True:
        user_input = input("Cmd: ").strip().split(maxsplit=1)
        
        if not user_input:
            continue
        
        option, url = user_input[0], user_input[1]
        url = url.replace("http://", "").replace("https://", "").split("/")[0]
        
        match option:
            case "block":
                with b_lock:
                    ban_list.add(url)
                print(f"Blocked {url}")
            case "unblock":
                with b_lock:
                    if url in ban_list:
                        ban_list.remove(url)
                        print(f"Unblocked {url}")
                    else:
                        print(f"{url} not in ban list")
            case _:
                print("Invalid command")

# main
if __name__ == "__main__":
    server()