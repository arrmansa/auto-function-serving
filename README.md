# auto-function-serving

A python package to offload a function call to an http server running on localhost automatically using a decorator. Compatible with multiprocessing, pickle, flask, fastapi, async etc..

## Why

Imagine a case of a multi threaded or multiprocessing application where 1 or few functions are heavily resource (cpu or memory) intensive, but the other functions can run in parallel.\
Example - an api call followed by tokenization and classification using a large DL model followed by further API calls.\
In such a case, it would make sense to create a server (generally using torchserve or tfserving) to serve requests, and replace the function call with a post request to the server.\
ServerHandler creates a **synchronous** server and replaces any calls to the function automatically during runtime.\
Requests are made to 1 instance of a process running a [http.server.HTTPServer](https://docs.python.org/3/library/http.server.html) which runs the function within it. Even calls made from different processes, threads, multiprocessing, flask, FastApi and async code are made to the same server process.\
Drawback - It might be slower than a 'proper' server and is restricted to 1 worker.
### AsyncServerHandler
AsyncServerHandler is also available which uses [aiohttp](https://docs.aiohttp.org/) to make the requests async, for use with fastapi and other async use cases. \
AsyncServerHandler has the same usage as ServerHandler, except calls need to be awaited or used with asyncio.run() or with asyncio.get_event_loop().run_until_complete().\
Number of async calls can be limited by setting AsyncServerHandler.TCPConnector_limit which controls the [TCPconnector](https://docs.aiohttp.org/en/stable/client_reference.html?highlight=connector#aiohttp.TCPConnector) limit (default 100) or by using [Semaphore](https://docs.python.org/3/library/asyncio-sync.html#asyncio.Semaphore)

## Usage

In general : 
```
some code with a callable
```
can be replaced with an instance of Either ServerHandler or AsyncserverHandler that accepts the code as a string in it's first argument and the name of the callable as the second argument.
```python
from auto_function_serving.ServerHandler import ServerHandler
callable_name = ServerHandler("""
some independent code with a callable
""", "callable_name")
```
Complete arguments
```python
from auto_function_serving.ServerHandler import ServerHandler
callable_name = ServerHandler("""
some independent code with a callable
""", "callable_name", port=None, backend='Popen', wait=100, backlog = 1024))
```
1. port
    * if None, then the input code is hashed and a port is chosen from 50000 to 60000 using the hash
    * if int, then int is chosen
    * otherwise, a random open port is chosen
2. backend - either 'Popen' or 'multiprocessing'
3. wait - approx max number of seconds to wait for the server to run. No waiting done if set to 0, default 100
4. backlog - max number of backlogged requests before returning errors, python default is 5, but default in ServerHandler is 1024.


Example :
```python
import module1
import module2
def functionname(someinput):
    a = module1.function1(someinput)
    return module2.function2(a)
```
can be replaced with
```python
from auto_function_serving.ServerHandler import AsyncserverHandler
functionname = AsyncServerHandler("""
import module1
import module2
def functionname(someinput):
    a = module1.function1(someinput)
    return module2.function2(a)
""", "functionname", port="Any")
```
Decorators for functions (@AsyncserverHandler.decorator and @ServerHandler.decorator) are also provided, but don't work in some cases. Details in more usage.

## Installation

Use the package manager pip to install [auto_function_serving](https://pypi.org/project/auto-function-serving/)
```bash
pip install auto_function_serving
```

## How does this work?
Code for the server is stored in [ServerHandler](https://github.com/arrmansa/auto-function-serving/blob/main/src/auto_function_serving/ServerHandler.py).base_code and inspect.cleandoc and some string formatting is used to fill in the blanks.\
The server process is started with Popen (or multiprocessing if specified). The first thing it does is import socket and bind the port - if it's not available the code stops after an exception. Therefore only 1 instance of the server runs at a time on a machine.\
We know the function is ready after we can recieve a valid get request from the server.\
Inputs and outputs are sent as bytes, converted to and from objects using pickle.\
If port is None in while initializing (default), a port from 50000 to 60000 is chosen by hashing the input code to make it independent of the source of a function. Collisions of different functions are possible, but unlikely. The collision of the same function in multiple processes is used to make sure only 1 server process runs at a time. The port can be specified if needed.

## Performance (On my machine)
overhead for small input and output (few bytes) - \
~2ms for requests with urllib.request\
~5ms for async requests with aiohttp.ClientSession \
overhead for large input and output\
~10ms for 0.5 mb input and output (1mb total transfer).\
~60ms for 5 mb input and output (10 mb total transfer).\
~600ms for 50 mb input and output (100 mb total transfer).

## More Usage

It can also be used with the provided decorator for functions with no dependencies outside the function.
```python
from auto_function_serving.ServerHandler import ServerHandler
@ServerHandler.decorator
def someheavyfunction(args,**kwargs):
    for i in range(big_number)
        someexpensivecomputation
```
imports inside the function will work
```python
from auto_function_serving.ServerHandler import ServerHandler
@ServerHandler.decorator
def someheavyfunction(args,**kwargs):
    import numpy as np
```
```python
from auto_function_serving.ServerHandler import ServerHandler
@ServerHandler.decorator
def someheavyfunction(args,**kwargs):
	if not hasattr(someheavyfunction,'RunOnce'):
	global np
	import numpy as np
	setattr(someheavyfunction,'RunOnce',None)
	... etc
```

When the somemodule does not have any expensive global loading.
```python
from auto_function_serving.ServerHandler import ServerHandler
from somemodule import someheavyfunction
someheavyfunction = ServerHandler.decorator(someheavyfunction)
```
Ip address can be changed by setting ServerHandler.ip_address (default "127.0.0.1")

## Other things to look into
Libraries : Celery, Tfserving, Torchserve, Flask\
Sending globals and locals to exec\
ast trees

## Contributing
Pull requests are welcome.

## License
[Apache License 2.0](https://choosealicense.com/licenses/apache-2.0/)