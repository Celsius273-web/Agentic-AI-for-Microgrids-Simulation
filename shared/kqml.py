from kqml import KQMLPerformative, KQMLList
from google.adk.agents import Agent

class kqml:
    @staticmethod
    def parse_message(raw_kqml: str):
        """Parses raw string into a structured object."""
        return KQMLPerformative.from_string(raw_kqml)

    @staticmethod
    def create_message(verb: str, content: str, sender: str, receiver: str):
        """Ensures consistent KQML formatting for outgoing messages."""
        perf = KQMLPerformative(verb)
        perf.set('content', content)
        perf.set('sender', sender)
        perf.set('receiver', receiver)
        return perf.to_string()