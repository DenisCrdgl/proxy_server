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