import importlib
import unittest


class AgentIsolationTest(unittest.TestCase):
    def test_agents_are_isolated_per_user_and_session(self):
        main = importlib.import_module('main')

        class DummyAgent:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

        original_agent = main.Agent
        original_cache = getattr(main, '_agent_cache', None)

        try:
            main.Agent = DummyAgent
            main._agent_cache = {}
            main.get_memory_session_manager = lambda session_id, user_id: object()
            main.get_streamable_http_mcp_client = lambda: None
            main.get_gateway_mcp_client = lambda auth_header: object()
            main.load_model = lambda: object()

            agent_a = main.get_or_create_agent('session-1', 'alice', 'Bearer token-a')
            agent_b = main.get_or_create_agent('session-1', 'bob', 'Bearer token-b')
            agent_c = main.get_or_create_agent('session-2', 'alice', 'Bearer token-c')

            self.assertIsNot(agent_a, agent_b)
            self.assertIsNot(agent_a, agent_c)
            self.assertIsNot(agent_b, agent_c)
        finally:
            main.Agent = original_agent
            if original_cache is None:
                delattr(main, '_agent_cache')
            else:
                main._agent_cache = original_cache
