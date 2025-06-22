import pickle
from tornado import gen
from tornado.ioloop import IOLoop
from tornado.tcpclient import TCPClient


class Client(TCPClient):
    msg_separator = b'\r\n'

    @gen.coroutine
    def run(self, host, port):
        stream = yield self.connect(host, port)
        while True:
            data = yield stream.read_until(self.msg_separator)
            body = data.rstrip(self.msg_separator)
            packet = pickle.loads(body)
            print(body)


if __name__ == '__main__':
    Client().run('localhost', 8766)
    print('Connecting to server socket...')
    IOLoop.instance().start()
    print('Socket has been closed.')
