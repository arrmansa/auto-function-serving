# auto-function-serving

A python package to offload a function call to an http server running on localhost automatically using a decorator. Compatible with multiprocessing, pickle, flask, fastapi, async etc..

## Why

Imagine a case of a multi threaded or multiprocessing application where 1 or few functions are heavily resource (cpu or memory) intensive, but the other functions can run in parallel.\
Example - an api call followed by tokenization and classification using a large DL model followed by further API calls.\
In such a case, it would make sense to create a server (generally using torchserve or tfserving) to serve requests, and replace the function call with a post request to the server.\
ServerHandler does this automatically during runtime. (Although it might be slower than a 'proper' server)\
AsyncServerHandler is also available which uses [aiohttp](https://docs.aiohttp.org/) to make the requests async, for use with fastapi and other async use cases.
AsyncServerHandler has the same usage as ServerHandler, except calls need to have await before it.
 
## Reccomended Usage
When the somemodule does not have any expensive global loading.
```python
from auto_function_serving.ServerHandler import ServerHandler
from somemodule import someheavyfunction
someheavyfunction = ServerHandler.decorator(someheavyfunction)
```
if there is some global loading
```python
from auto_function_serving.ServerHandler import ServerHandler
someheavyfunction = ServerHandler("""
from somemodule import someheavyfunction
""", "someheavyfunction")
```
Any calls to this new **someheavyfunction** will make requests to 1 instance of a process running a [http.server.HTTPServer](https://docs.python.org/3/library/http.server.html) which runs the function within it. Even calls made from different processes, threads, multiprocessing or servers like flask.\
It can also be used like a traditional decorator for functions with no dependencies outside the function.
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
but the better way to do it might be
```python
from auto_function_serving.ServerHandler import ServerHandler
someheavyfunction = ServerHandler("""
import numpy as np
def someheavyfunction(args,**kwargs):
	np.ones(1000) 
	...
""", "someheavyfunction")
```
## Installation

Use the package manager pip to install [auto_function_serving](https://pypi.org/project/auto-function-serving/)
```bash
pip install auto_function_serving
```

## More Usage
In general : 
```
some independent code with a callable
```
can be replaced with 
```python
from auto_function_serving.ServerHandler import ServerHandler
callable_name = ServerHandler("""
some independent code with a callable
""", "callable_name")
```

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
from auto_function_serving.ServerHandler import ServerHandler
functionname = ServerHandler("""
import module1
import module2
def functionname(someinput):
    a = module1.function1(someinput)
    return module2.function2(a)
""", "functionname")
```
# How does this work?
Code for the server is stored in ServerHandler.base_code, inspect.cleandoc and some string formatting is used to fill in the blanks.\
A port from 50000 to 60000 is chosen by hashing the input text to make it independent of the source of a function. Collisions are possible, but unlikely. The port can be specified if needed.
```python
from somemodule import someheavyfunction
from auto_function_serving.ServerHandler import ServerHandler
someheavyfunction = ServerHandler.decorator(someheavyfunction, port = 4321)
```
ServerHandler.ip_address is set as "127.0.0.1".\
The server process is started with Popen (or multiprocessing if specified), and the first thing it does is import socket and bind the port - if it's not available the code stops after an exception. Therefore only 1 instance of the server runs at a time on a machine.\
We know the function is ready after we can recieve a valid get request from the server.\
Inputs and outputs are sent as bytes, converted to and from objects using pickle.

## Performance (On my machine)
overhead for small input and output (few bytes) - \
~2ms for requests with urllib.request\
~5ms for async requests with aiohttp.ClientSession \
overhead for large input and output\
~10ms for 0.5 mb input and output (1mb total transfer).\
~60ms for 5 mb input and output (10 mb total transfer).\
~600ms for 50 mb input and output (100 mb total transfer).

## Other things to look into
Libraries : Celery, Tfserving, Torchserve, Flask\
Sending globals and locals to exec\
ast trees

## Contributing
Pull requests are welcome.

## License
[Apache License 2.0](https://choosealicense.com/licenses/apache-2.0/)
