from jev_series_client import JevSettings


def test_jev_key_alias_and_legacy_fallback(monkeypatch):
    monkeypatch.setenv('TYPESAFE_API_KEY','synthetic-legacy')
    monkeypatch.setenv('JEV_API_KEY','synthetic-jev')
    assert JevSettings().api_key=='synthetic-jev'
    monkeypatch.setenv('JEV_API_KEY','')
    assert JevSettings().api_key=='synthetic-legacy'
