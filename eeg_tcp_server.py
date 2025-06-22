import pickle
from tornado.tcpserver import TCPServer
from tornado.iostream import StreamClosedError, IOStream
from eeg_signal_generator import EegSignalGenerator
from asyncio import sleep
import traceback

class EegTcpServer(TCPServer):
    message_separator = b'\r\n'
    def __init__(self, eeg_signal_generator: EegSignalGenerator):
        super().__init__()
        self.eeg_signal_generator = eeg_signal_generator

    async def handle_stream(self, stream, address):
        timer = self.eeg_signal_generator.start_generating_signals(lambda packet: self.send_data(packet, stream))

        while timer.is_running():
            await sleep(0.05)


    async def send_data(self, packet, stream: IOStream):
        request = stream.read_until(self.message_separator)
        packet_bytes = pickle.dumps(packet)
        await stream.write(packet_bytes)
