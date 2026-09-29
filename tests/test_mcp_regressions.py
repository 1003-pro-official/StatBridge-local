from statbridge_mcp.metadata_store import normalize_frequency
from statbridge_mcp.statistics_service import _local_frequency_values


def test_annual_frequency_accepts_kosis_a_and_y_codes():
    assert normalize_frequency("A") == "Y"
    assert _local_frequency_values("A") == {"A", "Y"}


def test_kosis_response_with_unescaped_backslash_is_readable():
    from statbridge_mcp.kosis_client import _loads_lenient

    assert _loads_lenient('{"label":"A\\q"}') == {"label": "A\\q"}
