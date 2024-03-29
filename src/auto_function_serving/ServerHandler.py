# Core functionality
import pickle
from multiprocessing import Process
import sys
from subprocess import Popen
import urllib.request
import time
# Convenience
import random
import socket
import inspect
import atexit
import hashlib
import logging
# For Async
import asyncio
import aiohttp

# TODO - build a function to return a class that inherits from ServerHandler and allows user to configure more options
# def advanced_decorator():
#     class returnableclass(ServerHandler):
#         #someonfigurationere
#         return returnableclass
# TODO - Add documentation and simplify code
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
    import sys
    sys.path = pickle.loads({pickle_sys_path})

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
        def log_message(*args,**kwargs):
            return None
    #Run
    tempsocket.close()
    httpd = HTTPServer(("{ip_address}", {port}), functionserver)
    httpd.serve_forever()""")

    ip_address = "127.0.0.1"

    @staticmethod
    def get_specific_port(text, minimum=50000, maximum=60000):
        hashbytes = hashlib.md5(text.encode()).digest()
        port = minimum + int.from_bytes(hashbytes, "big") % (maximum - minimum)
        return port

    @staticmethod
    def get_free_port(ip_address):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((ip_address, 0))
            ip_addr, port = s.getsockname()
            return port

    @staticmethod
    def port_inuse(ip_address, port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((ip_address, port))
                return False
            except OSError:
                logging.warning(f"port {port} is in use")
                return True

    @classmethod
    def decorator(cls, func, port=None, backend='Popen', wait=100, backlog=1024):
        # assert hasattr(func, '__call__'), "Decorated object should be callable"
        # Get globals to prevent recursive starting of servers
        if hasattr(func, '__globals__'):
            globals = func.__globals__  # PROBABLY A FUNCTION
        elif hasattr(func.__call__, '__globals__'):
            globals = func.__call__.__globals__  # PROBABLY A CLASS
        else:
            globals = None

        if func.__module__ != '__main__' and cls.__module__ not in str(globals):
            # Import module if possible
            function_code = f"from {func.__module__} import {func.__name__}"
        else:  # try to get the function code and remove the decorator
            function_code = inspect.cleandoc('\n' + inspect.getsource(func))
            decorator_string = f'@{cls.__name__}.decorator\n'
            if -1 < function_code.find(decorator_string) < function_code.find(f" {func.__name__}"):
                function_code = function_code.replace(decorator_string, "", 1)
            # TODO - pass globaldict to the server if possible, add option to do it
            # TODO - maybe use ast and inspect.getsourcefile() to add the rest of the code to make it work
        return cls(function_code, func.__name__, port=port, backend=backend, wait=100, backlog=1024)

    def start_server_process(self, server_code, backend):
        logging.info(f'using backend {backend}')
        logging.info("SERVER CODE IS - \n" + server_code.replace('\n', '\\n'))
        if backend == 'multiprocessing':
            try:
                server_process = Process(target=exec, args=(server_code, {}))
                server_process.start()
            except RuntimeError as e:
                logging.error(str(e))
                logging.warning("Attempting to disable multiprocessing check")
                from multiprocessing import spawn
                spawn._check_not_importing_main = lambda: None
                server_process = Process(target=exec, args=(server_code, {}))
                server_process.start()
        elif backend == 'Popen':
            if 'python' in sys.executable:
                server_process = Popen([sys.executable, "-c", server_code], shell=False)
            else:
                logging.warning(f"sys.executable is {sys.executable}, using default python")
                server_process = Popen(["python", "-c", server_code])
        else:
            logging.error(f"Unknown Backend {backend}")
            raise ValueError(f"Unknown Backend {backend}")
        return server_process

    def __init__(self, callable_code, callable_name, port=None, backend='Popen', wait=100, backlog=1024):
        self.callable_code = callable_code
        self.callable_name = callable_name
        self.backend = backend
        self.wait = wait
        self.backlog = backlog
        if port is None:
            self.port = self.get_specific_port(callable_code)
        elif not isinstance(port, int):
            self.port = self.get_free_port(self.ip_address)
        else:
            self.port = port
        logging.info(f"using port {port} for {callable_name}")
        self.server_address = f'http://{self.ip_address}:{self.port}'
        self.server_code = self.base_code.format(pickle_sys_path = pickle.dumps(sys.path), 
                                                 callable_code=inspect.cleandoc('\n' + callable_code),
                                                 callable_name=callable_name, backlog=self.backlog,
                                                 ip_address=self.ip_address, port=self.port)

        if wait and not self.port_inuse(self.ip_address, self.port):
            # slight delay so that multiple processes do not collide, but it is fine even if they do.
            time.sleep(random.random())

        if not self.port_inuse(self.ip_address, self.port):
            self.server_process = self.start_server_process(self.server_code, self.backend)
        else:
            self.server_process = None
            logging.info(f"can't bind port {self.port}, server might be running")

        if wait:
            logging.info("Waiting for server to start")
            for attempt in range(wait + 1):
                time_limit = min(1, 0.01*(2**attempt))
                try:
                    urllib.request.urlopen(self.server_address).close()
                    break
                except:
                    assert attempt < wait, "Could not connect to server before timeout"
                    time.sleep(time_limit)
        logging.info(f"{callable_name} is on {self.server_address}")
        atexit.register(self.__del__) #Need more cleanup for these things

    def __call__(self, *args, **kwargs):
        with urllib.request.urlopen(self.server_address, pickle.dumps((args, kwargs))) as f:
            return pickle.loads(f.read())

    def killserverprocess(self):
        try: self.server_process.kill()
        except: pass
        try: self.server_process.terminate()
        except: pass
        try: self.server_process.close()
        except: pass

    # Try everything to kill the stray popen or multiprocessing process
    def __del__(self):
        self.killserverprocess()
        atexit.unregister(self.__del__)

    def __getstate__(self):
        d = {}
        d["callable_code"] = self.callable_code
        d["callable_name"] = self.callable_name
        d["port"] = self.port
        d["backend"] = self.backend
        d["wait"] = self.wait
        d["backlog"] = self.backlog
        d["ip_address"] = self.ip_address
        return d

    def __setstate__(self, d):
        self.ip_address = d["ip_address"]
        self.__init__(d["callable_code"], d["callable_name"], d["port"],
                      d["backend"], d["wait"], d["backlog"])


class AsyncServerHandler(ServerHandler):

    TCPConnector_limit = 100  # default limit

    def __init__(self, callable_code, callable_name, port=None, backend='Popen', wait=100, backlog=1024):
        super().__init__(callable_code, callable_name, port=port, backend=backend, wait=wait, backlog=backlog)
        try:
            connector = aiohttp.TCPConnector(limit=self.TCPConnector_limit)
            self.ClientSession = aiohttp.ClientSession(raise_for_status=True, connector=connector)
        except:
            pass

    async def __call__(self, *args, **kwargs):
        send_bytes = pickle.dumps((args, kwargs))
        try:
            return await self.get_objects(send_bytes)
        except RuntimeError as e:
            logging.warning(f"Possible event loop issue: {e}")
            self.clientsessioncloser()
        except AttributeError as e:
            logging.warning(f"ClientSession missing, probably eventloop not started before: {e}")
        connector = aiohttp.TCPConnector(limit=self.TCPConnector_limit)
        self.ClientSession = aiohttp.ClientSession(raise_for_status=True, connector=connector)
        return await self.get_objects(send_bytes)

    async def get_objects(self, send_bytes):
        async with self.ClientSession.post(self.server_address, data=send_bytes, ssl=False) as response:
            return pickle.loads(await response.read())

    # Try everything to end ClientSession
    def clientsessioncloser(self):
        try: asyncio.run(self.ClientSession.close())
        except: pass
        try: self.ClientSession.connector.close()
        except: pass
        try: self.ClientSession.detach()
        except: pass

    def __del__(self):
        self.clientsessioncloser()
        super().__del__()

    def __getstate__(self):
        d = super().__getstate__()
        d["TCPConnector_limit"] = self.TCPConnector_limit
        return d

    def __setstate__(self, d):
        super().__setstate__(d)
        self.TCPConnector_limit = d["TCPConnector_limit"]
        try:
            connector = aiohttp.TCPConnector(limit=self.TCPConnector_limit)
            self.ClientSession = aiohttp.ClientSession(raise_for_status=True, connector=connector)
        except:
            pass
