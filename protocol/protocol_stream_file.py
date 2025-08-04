import json
from typing import Dict, Any, List
from protocol.protocol_stream_interface import ProtocolStreamReaderProtocol
from protocol.types import SignalChunk

class ProtocolStreamFile(ProtocolStreamReaderProtocol):
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.signal_data: Any = {}  # Can be Dict or List depending on JSON structure
        self.current_index = 0
        self._load_json_file()

    def _load_json_file(self) -> None:
        """Load the JSON file and store it in a dictionary variable"""
        try:
            with open(self.file_path, 'r') as file:
                # Read the entire JSON file into a dictionary/list
                self.signal_data = json.load(file)
                print(f"Successfully loaded {len(self.signal_data)} signal frames from {self.file_path}")
        except FileNotFoundError:
            raise FileNotFoundError(f"JSON file not found: {self.file_path}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON format in {self.file_path}: {e}")
        except Exception as e:
            raise Exception(f"Error reading JSON file {self.file_path}: {e}")

    def get_signal_data(self) -> Dict[str, Any]:
        """Return the loaded signal data dictionary"""
        return self.signal_data

    def get_signal_frames(self) -> List[Dict[str, Any]]:
        """Return the list of signal frames if the JSON contains an array"""
        if isinstance(self.signal_data, list):
            return self.signal_data
        else:
            return [self.signal_data]

    def get_frame_count(self) -> int:
        """Return the number of signal frames"""
        if isinstance(self.signal_data, list):
            return len(self.signal_data)
        else:
            return 1

    def __aiter__(self):
        return self

    async def __anext__(self) -> SignalChunk:
        # Implementation for streaming signal chunks
        if isinstance(self.signal_data, list) and self.current_index < len(self.signal_data):
            frame = self.signal_data[self.current_index]
            self.current_index += 1
            # Create SignalChunk with the required fields
            return SignalChunk(
                timestamp=frame.get('timestamp', 0.0),
                window_ms=frame.get('window_ms', 1000),
                channels=frame.get('channels', []),
                units=frame.get('units', 'uV'),
                matrix=frame.get('matrix', [])
            )
        else:
            raise StopAsyncIteration
