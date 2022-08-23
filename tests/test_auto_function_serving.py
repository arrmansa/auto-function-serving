from auto_function_serving.ServerHandler import ServerHandler, AsyncServerHandler
from multiprocessing import Pool
import pickle
import asyncio
import time

import unittest

class alltests(unittest.TestCase):
    def test_everything(self):
        def servers_running():
            return [ServerHandler.port_inuse(ServerHandler.ip_address, port) for port in (1234, 58604, 52881)]
        assert servers_running() == [False, False, False], f"SERVERS ARE RUNNING, {servers_running()}"
            
        return_one = ServerHandler("""
        def return_one():
            return 1
        ""","return_one", port = 1234, backend='multiprocessing')

        @ServerHandler.decorator
        def fact(n, somesting = "Default"):
            if n < 0:
                return somesting
            if n == 0:
                return 1
            return n * fact(n -1)

        @AsyncServerHandler.decorator
        def stringreverseextra(to_reverse, extra = "MORE THINGS"):
            return to_reverse[::-1] + extra

        ports_used = (return_one.port, stringreverseextra.port, fact.port)
        assert ports_used == (1234, 58604, 52881), f"Wrong ports used, {str(ports_used)}"

        assert servers_running() == [True, True, True], f"SERVERS ARE NOT RUNNING, {servers_running()}"

        a,b,c = pickle.dumps(fact), pickle.dumps(stringreverseextra), pickle.dumps(return_one)

        assert return_one() == 1, "NEEDS TO RETURN ONE"
        assert asyncio.run(stringreverseextra("CBA", extra="DEF")) == "ABCDEF", "Async or kwargs failed"
        with Pool(5) as p:
            assert p.map(fact, [-1 , 2, 3, 4, 5]) == ['Default', 2, 6, 24, 120]
        async_call = stringreverseextra("CBA", extra="DEF")
        assert str(type(async_call)) == "<class 'coroutine'>"; "Is not a coroutine"
        assert asyncio.run(async_call) == "ABCDEF", "Async or kwargs failed"
        
        print("ALL FUNCTION CALLS WORKED")

        #DELETE
        return_one.__del__()
        stringreverseextra.__del__()
        fact.__del__()

        start_time = time.time()
        while servers_running() != [False, False, False]:
            time.sleep(1)
            print(servers_running())
            assert time.time() - start_time < 20, "Too much time to close a server"

        assert servers_running() == [False, False, False], f"SERVERS ARE RUNNING AFTER CLOSE COMMAND, {servers_running()}"

        print("CLOSING SERVERS WORKED")

        return_one = pickle.loads(c)
        fact = pickle.loads(a)
        stringreverseextra = pickle.loads(b)

        assert return_one() == 1, "NEEDS TO RETURN ONE"
        assert asyncio.run(stringreverseextra("CBA", extra="DEF")) == "ABCDEF", "Async or kwargs failed"
        with Pool(5) as p:
            assert p.map(fact, [-1 , 2, 3, 4, 5]) == ['Default', 2, 6, 24, 120]
        async_call = stringreverseextra("CBA", extra="DEF")
        assert str(type(async_call)) == "<class 'coroutine'>"; "Is not a coroutine"
        assert asyncio.run(async_call) == "ABCDEF", "Async or kwargs failed"
        
        print("ALL FUNCTION CALLS WORKED")

if __name__ == '__main__':
    unittest.main()