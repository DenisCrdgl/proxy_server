import threading
import socket
import ssl
import time
from urllib.parse import urlparse

cache = {}
ban_list = set()
c_lock = threading.Lock()
b_lock = threading.Lock()

# constants
PORT = 8080
BUFF_SIZE = 4096
CACHE_TIME = 60

def host(url):
    if not url.startswith("http"):
        url = "http://" + url
    parsed_url = urlparse(url)
    return parsed_url.hostname.lower() if parsed_url.hostname else url.lower()

def client_handler(cl_sock, cl_add):
    try:
        req = cl_sock.recv(BUFF_SIZE)
        if not req:
            cl_sock.close()
            return
        msg_info = req.split(b'\n')[0]
        method, url, _ = msg_info.decode().split()
        print(f"Request from {cl_add} from {url} using {method}")
        
        if method == "CONNECT":
            https_handler(cl_sock, url)
        else:
            http_req_handler(cl_sock, req, url)
    except Exception as e:
        print(f"Client handling error: {e}")
    finally:
        cl_sock.close()

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
    
    strt_time = time.time()
    
    with c_lock:
        if url in cache and time.time() - cache[url][1] < CACHE_TIME:
            response = cache[url][0]
            print(f"{url} found in cache")
            cl_sock.send(response)
            print(f"Time: {time.time() - strt_time:.3f} seconds")
            return
    
    print(f"{url} not found in cache")
    
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
            
        print(f"Operation took {time.time() - strt_time:3f} seconds to retrieve")
        
        server_sock.close()
        
    except Exception as e:
        print(f"HTTP handler error {e}")
        cl_sock.send(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
        
def https_handler(cl_sock, url):
    try:
        
        host, port = url.split(":")
        
        with b_lock:
            if blocked(host):
                print(f"Blocked {host}")
                cl_sock.send(b"HTTP/1.1 403 Forbidden\r\n\r\n")
                return
            
        print(f"Connecting to {host}:{port}")
        sock = socket.create_connection((host, port))
        cl_sock.send(b"HTTP/1.1 200 Connection Established\r\n\r\n")
        
        threading.Thread(target=send, args=(cl_sock, sock)).start()
        send(sock, cl_sock)
        
    except Exception as e:
        print(f"Unable to connect {e}")
        cl_sock.send(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
      
def server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('0.0.0.0', PORT))
    server.listen(100)
    print(f"Proxy server listening on port {PORT}...")
    
    threading.Thread(target=server_options, daemon=True).start()
    
    while True:
        cl_sock, cl_add = server.accept()
        thread = threading.Thread(target=client_handler, args = (cl_sock, cl_add), daemon=True).start()

def blocked(host):
    host = host.lower()
    return any(host == banned or host.endswith("." + banned) for banned in ban_list)
     
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

if __name__ == "__main__":
    server()