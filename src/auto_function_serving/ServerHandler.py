#Core functionality
import pickle
from multiprocessing import Process
from subprocess import Popen
import urllib.request
import time
#Convenience 
import socket
import inspect
import atexit
import hashlib
import logging
#For Async
import asyncio
import aiohttp

# TODO - build a function to return a class that inherits from ServerHandler and allows user to configure more options
# def advanced_decorator():
#    class returnableclass(ServerHandler):
#        #someonfigurationere
#    return returnableclass

# TODO - build a class that inherits from ServerHandler and allows user to run multiple instances of the function

        
class ServerHandler():

    base_code = inspect.cleandoc("""
    #Grab port
    import socket
    tempsocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tempsocket.bind(("{ip_address}", {port}))
    #Minimum import
    from http.server import HTTPServer, BaseHTTPRequestHandler
    import pickle
    #Maximum socket backlog, is 5 by default
    #https://docs.python.org/3/library/socket.html#socket.socket.listen
    import socketserver
    socketserver.TCPServer.request_queue_size = {backlog}
    #Function to serve

    # TODO - catch exceptions in callable_code and handle it (maybe tempsocket.close() or sys.exit()
    {callable_code}

    #Server
    class functionserver(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
        def do_POST(self):
            #INPUT
            content_len = int(self.headers.get('Content-Length'))
            args, kwargs = pickle.loads(self.rfile.read(content_len))
            #FUNCTION CALL
            output_to_return = {callable_name}(*args,**kwargs)
            #OUTPUT
            self.send_response(200)
            self.end_headers()
            self.wfile.write(pickle.dumps(output_to_return))
    #Run
    tempsocket.close()
    httpd = HTTPServer(("{ip_address}", {port}), functionserver)
    httpd.serve_forever()""")

    ip_address = "127.0.0.1"

    @staticmethod
    def get_specific_port(source_code, minimum=50000, maximum=60000):
        hashbytes = hashlib.md5(source_code.encode()).digest()
        port = minimum + int.from_bytes(hashbytes, "big") % (maximum - minimum)
        return port

    @staticmethod
    def get_free_port(ip_address):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((ip_address, 0))
            ip_addr, port = s.getsockname()
            return port

    @staticmethod
    def port_inuse(ip_address,port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((ip_address, port))
                return False
            except OSError:
                logging.warning(f"port {port} is in use")
                return True

    @classmethod
    def decorator(cls, func, port=None, backend='multiprocessing', wait=True, backlog = 1024):
        # assert hasattr(func, '__call__'), "decorated object should be callable"  #possible check to be added
        if hasattr(func, '__globals__'):
            globaldict = func.__globals__  # PROBABLY A FUNCTION
        elif hasattr(func.__call__, '__globals__'):
            globaldict = func.__call__.__globals__  # PROBABLY A CLASS
        else:
            globaldict = None
        if func.__module__ != '__main__' and cls.__module__ not in str(globaldict):
            function_code = f"from {func.__module__} import {func.__name__}"
        else:
            function_code = inspect.cleandoc('\n' + inspect.getsource(func))
            decorator_string = f'@{cls.__name__}.decorator\n'
            if -1 < function_code.find(decorator_string) < function_code.find(f" {func.__name__}"):
                function_code = function_code.replace(decorator_string, "", 1)
            # TODO - pass globaldict to the server if possible, add option to do it
            # TODO - maybe use ast and inspect.getsourcefile() to add the rest of the code to make it work
        return cls(function_code, func.__name__, port=port, backend=backend, wait=wait, backlog = 1024)

    # Default backend is multiprocessing because Popen doesn't open python in same env
    @staticmethod
    def run_code_async(server_code, backend):
        logging.info(f'using backend {backend}')
        logging.info("SERVER CODE IS - \n" + server_code.replace('\n', '\\n'))
        if backend == 'Popen':
            server_process = Popen(["python", "-c", server_code])
        elif backend == 'multiprocessing':
            server_process = Process(target=exec, args=(server_code, {}))
            server_process.start()
        else:
            logging.error(f"Unknown Backend {backend}")
            raise ValueError(f"Unknown Backend {backend}")
        return server_process

    def __init__(self, callable_code, callable_name, port=None, backend='multiprocessing', wait=True, backlog = 1024):
        if port is None:
            self.port = self.get_specific_port(callable_code)
        elif not isinstance(port, int):
            self.port = get_free_port(self.ip_address)
        else:
            self.port = port

        logging.info(f"using port {port} for {callable_name}")
        self.server_address = f'http://{self.ip_address}:{self.port}'

        self.backend = backend
        self.server_code = self.base_code.format(callable_code=inspect.cleandoc('\n' + callable_code),
                                                 callable_name=callable_name, backlog = backlog,
                                                 ip_address=self.ip_address, port=self.port)
        if not self.port_inuse(self.ip_address, self.port):
            self.server_process = self.run_code_async(self.server_code, self.backend)
            atexit.register(self.__del__)  # Killing the run_code_async process is hard
        else:
            self.server_process = None
            logging.warning(f"port {self.port} not available to bind, server not started from here")

        if wait:
            for attempt in range(100):
                try: urllib.request.urlopen(self.server_address).close(); break
                except: assert attempt < 99; time.sleep(min(1, 0.01*(2**attempt)))

    def __call__(self, *args, **kwargs):
        with urllib.request.urlopen(self.server_address, pickle.dumps((args, kwargs))) as f:
            return pickle.loads(f.read())

    # Try everything to kill the stray popen or multiprocessing process
    def __del__(self):
        try: self.server_process.kill()
        except: pass
        try: self.server_process.terminate()
        except: pass
        try: self.server_process.close()
        except: pass
        atexit.unregister(self.__del__)
        
    def __getstate__(self):
        return {"port": self.port, "server_address": self.server_address,
                "backend": self.backend, "server_code": self.server_code}

    def __setstate__(self, d):
        self.server_address = d["server_address"]
        self.backend = d["backend"]
        self.server_code = d["server_code"]
        self.server_process = None


class AsyncServerHandler(ServerHandler):

    async def __call__(self, *args, **kwargs):
        response = await self.ClientSession.post(self.server_address, data = pickle.dumps((args, kwargs)))
        async with response:
            return pickle.loads(await response.read())
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args,**kwargs)
        self.ClientSession = aiohttp.ClientSession(raise_for_status=True)
        
    def __setstate__(self, *args, **kwargs):
        super().__setstate__(*args,**kwargs)
        self.ClientSession = aiohttp.ClientSession(raise_for_status=True)
        
    def __del__(self):
        try: asyncio.run(self.ClientSession.close())
        except: pass
        try: del self.ClientSession
        except: pass
        super().__del__()