"""Repeated ASGI shutdown must not reflush a stopped exporter queue."""
from statbridge_mcp import observability as obs


def test_exporter_shutdown_is_idempotent_and_stopped_client_is_not_reused(monkeypatch):
    class Client:
        calls=0
        def shutdown(self):
            self.calls+=1
            assert self.calls==1, 'A second SDK flush would wait on stopped consumers'
    client=Client()
    monkeypatch.setattr(obs,'_client',client);monkeypatch.setattr(obs,'_client_state','configured')
    monkeypatch.setenv('LANGFUSE_ENABLED','true')
    for key in ('LANGFUSE_PUBLIC_KEY','LANGFUSE_SECRET_KEY','LANGFUSE_BASE_URL'):monkeypatch.setenv(key,'isolated-test')
    obs.shutdown_exporter();obs.shutdown_exporter()
    assert client.calls==1
    assert obs.exporter()==(None,'shutdown')


def test_failed_exporter_shutdown_does_not_leave_a_reusable_client(monkeypatch):
    class Client:
        def shutdown(self):raise RuntimeError('isolated exporter failure')
    monkeypatch.setattr(obs,'_client',Client());monkeypatch.setattr(obs,'_client_state','configured')
    obs.shutdown_exporter()
    assert obs._client is None and obs._client_state=='shutdown'
    obs.shutdown_exporter()
