import threading
import socket
import ssl
import time

cache = {}
ban_list = set()
c_lock = threading.Lock()
b_lock = threading.Lock()

# constants
PORT = 8080
BUFF_SIZE = 4096
CACHE_TIME = 60

def client_handler(cl_sock, cl_add):
    try:
        req = cl_sock.recv(BUFF_SIZE)
        if not req:
            cl_sock.close()
            return
        msg_info = req.split(b'\n')[0]
        method, url, garbage = msg_info.decode().split()
        print(f"Request from {cl_add} from {url} using {method}")
        
        if method == "CONNECT":
            http_handler(cl_sock, url)
        else:
            http_handler(cl_sock, req, url)
    except Exception as e:
        print("Client handling error")
    finally:
        cl_sock.close()

def http_handler(cl_sock, req, url):
    with ban_list:
        if url in ban_list:
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
        http = url.find("://")
        location = url[(http + 3):] if http != -1 else url
        port = location.find(":")
        add = location.find("/")
        if add == -1:
            add = len(location)
        host = location[:min(port if port != -1 else add, add)]
        address = location[add:] if add < len(location) else "/"
        
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.connect((host, 80))
        server_sock.send(req)
        
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
        
def http_handler(cl_sock, url):
    try:
        
        host, port = url.split(":")
        port = int(port)
        print(f"Connecting to {host}:{port}")
        sock = socket.create_connection((host, port))
        cl_sock.send(b"HTTP/1.1 200 Connection Established\r\n\r\n")
        
        threading.Thread(target = send, args = (cl_sock, sock)).start()
        send(sock, cl_sock)
        
    except Exception as e:
        print(f"Unable to connect {e}")
        cl_sock.send(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
      
def server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(('0.0.0.0', PORT))
    server.listen(100)
    print(f"Proxy server listening on port {PORT}...")
    
    while True:
        cl_sock, cl_add = server.accept()
        thread = threading.Thread(target = client_handler, args = (cl_sock, cl_add))
        thread.daemon = True
        thread.start()

if __name__ == "__main__":
    server()