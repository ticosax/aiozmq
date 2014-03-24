import unittest
import asyncio
import aiozmq, aiozmq.rpc

from test import support  # import from standard python test suite


class MyException(Exception):
    pass


class MyHandler(aiozmq.rpc.AttrHandler):

    @aiozmq.rpc.method
    def func(self, arg):
        return arg + 1

    @aiozmq.rpc.method
    @asyncio.coroutine
    def coro(self, arg):
        return arg + 1
        yield

    @aiozmq.rpc.method
    def exc(self, arg):
        raise RuntimeError("bad arg", arg)

    @aiozmq.rpc.method
    @asyncio.coroutine
    def exc_coro(self, arg):
        raise RuntimeError("bad arg 2", arg)
        yield

    @aiozmq.rpc.method
    def generic_exception(self):
        raise MyException('additional', 'data')


class RpcTests(unittest.TestCase):

    def setUp(self):
        self.loop = aiozmq.ZmqEventLoop()
        asyncio.set_event_loop(None)
        self.client = self.server = None

    def tearDown(self):
        if self.client is not None:
            self.close(self.client)
        if self.server is not None:
            self.close(self.server)
        self.loop.close()

    def close(self, server):
        server.close()
        self.loop.run_until_complete(server.wait_closed())

    def make_rpc_pair(self):
        port = support.find_unused_port()

        @asyncio.coroutine
        def create():
            server = yield from aiozmq.rpc.start_server(MyHandler(),
                bind='tcp://127.0.0.1:{}'.format(port),
                loop=self.loop)
            client = yield from aiozmq.rpc.open_client(
                connect='tcp://127.0.0.1:{}'.format(port),
                loop=self.loop)
            return client, server

        self.client, self.server = self.loop.run_until_complete(create())

        return self.client, self.server

    def test_func(self):
        client, server = self.make_rpc_pair()

        @asyncio.coroutine
        def communicate():
            ret = yield from client.rpc.func(1)
            self.assertEqual(2, ret)
            client.close()
            yield from client.wait_closed()

        self.loop.run_until_complete(communicate())

    def test_exc(self):
        client, server = self.make_rpc_pair()

        @asyncio.coroutine
        def communicate():
            with self.assertRaises(RuntimeError) as exc:
                yield from client.rpc.exc(1)
            self.assertEqual(('bad arg', 1), exc.exception.args)

        self.loop.run_until_complete(communicate())

    def test_not_found(self):
        client, server = self.make_rpc_pair()

        @asyncio.coroutine
        def communicate():
            with self.assertRaises(aiozmq.rpc.NotFoundError) as exc:
                yield from client.rpc.unknown_method(1, 2, 3)
            self.assertEqual(('unknown_method',), exc.exception.args)

        self.loop.run_until_complete(communicate())

    def test_coro(self):
        client, server = self.make_rpc_pair()

        @asyncio.coroutine
        def communicate():
            ret = yield from client.rpc.coro(2)
            self.assertEqual(3, ret)

        self.loop.run_until_complete(communicate())

    def test_exc_coro(self):
        client, server = self.make_rpc_pair()

        @asyncio.coroutine
        def communicate():
            with self.assertRaises(RuntimeError) as exc:
                yield from client.rpc.exc_coro(1)
            self.assertEqual(('bad arg 2', 1), exc.exception.args)

        self.loop.run_until_complete(communicate())

    def test_not_found_empty_name(self):
        client, server = self.make_rpc_pair()

        @asyncio.coroutine
        def communicate():
            with self.assertRaises(ValueError) as exc:
                yield from client.rpc(1, 2, 3)
            self.assertEqual(('RPC method name is empty',), exc.exception.args)

        self.loop.run_until_complete(communicate())

    def test_not_found_empty_name_on_server(self):
        client, server = self.make_rpc_pair()

        @asyncio.coroutine
        def communicate():
            with self.assertRaises(aiozmq.rpc.NotFoundError) as exc:
                yield from client._proto.call('', (), {})
            self.assertEqual(('',), exc.exception.args)

        self.loop.run_until_complete(communicate())

    def test_generic_exception(self):
        client, server = self.make_rpc_pair()

        @asyncio.coroutine
        def communicate():
            with self.assertRaises(aiozmq.rpc.GenericError) as exc:
                yield from client.rpc.generic_exception()
            self.assertEqual(('rpc_test.MyException',
                             ('additional', 'data')),
                             exc.exception.args)

        self.loop.run_until_complete(communicate())


class AbstractHandlerTests(unittest.TestCase):

    def test___getitem__(self):

        class MyHandler(aiozmq.rpc.AbstractHandler):

            def __getitem__(self, key):
                return super().__getitem__(key)

        with self.assertRaises(KeyError):
            MyHandler()[1]

    def test_subclass(self):
        self.assertTrue(issubclass(dict, aiozmq.rpc.AbstractHandler))
        self.assertIsInstance({}, aiozmq.rpc.AbstractHandler)
        self.assertFalse(issubclass(object, aiozmq.rpc.AbstractHandler))
        self.assertNotIsInstance(object(), aiozmq.rpc.AbstractHandler)
