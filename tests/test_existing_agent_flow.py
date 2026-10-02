from pathlib import Path
import runpy


def test_existing_agent_flow():
    module = runpy.run_path(str(Path(__file__).with_name('TEST_AGENT_FLOW.py')))
    module['main']()
