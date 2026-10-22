"""Offline FastAPI harness for edit/follow-up modes.

Reuses the same boundary as bok-reproduction v1: real app, fixed provider,
blocked network, throwaway auth DB. Only the external data source and login
are replaced.
"""
from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
from contextlib import contextmanager, ExitStack
from pathlib import Path
from unittest.mock import patch

from e2e_common import ROOT


def _module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@contextmanager
def offline_app(provider_series):
    os.environ.update(PYTHON_DOTENV_DISABLED='1', STATBRIDGE_HYBRID_RETRIEVAL='0',
                      STATBRIDGE_JEV_ENABLED='0', LANGFUSE_TRACING_ENABLED='false',
                      MPLCONFIGDIR=str(Path(tempfile.gettempdir()) / 'statbridge-e2e-mpl'))
    for key in ('OPENAI_API_KEY', 'KOSIS_API_KEY', 'NCP_CLOVA_API_KEY', 'NCP_API_KEY',
                'CLOVA_STUDIO_API_KEY', 'LANGFUSE_PUBLIC_KEY', 'LANGFUSE_SECRET_KEY'):
        os.environ[key] = ''
    for rel in ('src/backend', 'src/agent', 'tests', 'eval/statbridge-golden/v2/scripts'):
        if str(ROOT / rel) not in sys.path:
            sys.path.insert(0, str(ROOT / rel))
    legacy = _module(ROOT / 'eval/statbridge-golden/v2/scripts/run.py', 'e2e_legacy_runner')
    from core import FrozenProvider

    class Source(FrozenProvider):
        def __init__(self, metadata):
            super().__init__(provider_series)
            self.metadata = metadata

        def __getattr__(self, name):
            return getattr(self.metadata, name)

    import io
    real_open = io.open

    def guarded_open(file, *args, **kwargs):
        if isinstance(file, (str, Path)):
            normalized = str(file).replace('\\', '/').casefold()
            if ('/data/tables/' in normalized or normalized.endswith('/.env')
                    or 'holdout_answers' in normalized or 'statbridge-evaluation-private' in normalized):
                raise PermissionError('evaluation source boundary: forbidden file')
        return real_open(file, *args, **kwargs)

    def no_network(*args, **kwargs):
        raise RuntimeError('offline external access blocked')

    with tempfile.TemporaryDirectory(prefix='e2e-auth-') as temp, ExitStack() as stack:
        os.environ['STATBRIDGE_AUTH_DB'] = str(Path(temp) / 'accounts.sqlite3')
        stack.enter_context(patch('io.open', guarded_open))
        stack.enter_context(patch('builtins.open', guarded_open))
        stack.enter_context(patch('requests.sessions.Session.request', no_network))
        stack.enter_context(patch('httpx.HTTPTransport.handle_request', no_network))
        stack.enter_context(patch('urllib.request.urlopen', no_network))
        import bridge_api
        from authenticated_client import TestClient
        from agent_runtime import StatBridgeAgent
        from mcp_gateway import McpToolGateway
        from ncp_clova_client import NcpClovaClient, NcpSettings
        from statbridge_mcp.statistics_service import StatisticsService
        provider = Source(StatisticsService(client=legacy.NoNetwork()))
        agent = StatBridgeAgent(McpToolGateway(provider), ncp_client=NcpClovaClient(NcpSettings(api_key='')))
        stack.enter_context(patch.object(bridge_api, 'service', provider))
        stack.enter_context(patch.object(bridge_api, 'agent', agent))
        with TestClient(bridge_api.app) as client:
            yield client, provider, bridge_api
