"""Launch StatBridge locally and drive one candidate through the browser."""
import argparse
import hashlib
import json
import os
import socket
import subprocess
import tempfile
import time
from pathlib import Path

from playwright.sync_api import sync_playwright
from core import apply_profile, read_xlsx_cells


def observed_series(chart, contracts):
    if len(chart) != len(contracts):
        raise ValueError('rendered series count differs from expected')
    result = []
    for actual, contract in zip(chart, contracts):
        if actual.get('unit') != contract['unit'] or actual.get('label') != contract['label']:
            raise ValueError('rendered label or unit differs from expected contract')
        frequency = contract['frequency']
        points = []
        for point in actual.get('points', []):
            date = str(point['date'])
            digits = ''.join(ch for ch in date if ch.isdigit())
            if frequency == 'M':
                period = digits[:6]
            elif frequency == 'Q':
                if len(digits) >= 6:
                    month = int(digits[4:6])
                    period = digits[:4] + 'Q' + str((month - 1) // 3 + 1)
                else:
                    period = date
            else:
                period = digits[:4]
            points.append({'period': period, 'value': str(point['value'])})
        result.append({key: contract[key] for key in ('table_id', 'item_id', 'classifications', 'frequency', 'unit')} |
                      {'points': points})
    return result


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def run_case(product_root, bundle_root, case, run_dir, username, password):
    product_root, run_dir = Path(product_root).resolve(), Path(run_dir).resolve()
    bundle_root = Path(bundle_root).resolve()
    run_dir.mkdir(parents=True, exist_ok=True)
    api_port, web_port = free_port(), free_port()
    auth_db = run_dir / 'accounts.sqlite3'
    product_python = (product_root / '.venv/Scripts/python.exe' if os.name == 'nt'
                      else product_root / '.venv/bin/python')
    if not product_python.exists():
        raise FileNotFoundError('product checkout .venv Python was not found')
    env = os.environ.copy()
    env.update(PYTHONPATH=os.pathsep.join([str(product_root / 'src/backend'), str(product_root / 'src/agent')]),
               PYTHON_DOTENV_DISABLED='1', STATBRIDGE_API_PORT=str(api_port), STATBRIDGE_AUTH_DB=str(auth_db),
               STATBRIDGE_DATA_DIR=str(bundle_root / 'build_inputs/processed'),
               STATBRIDGE_TABLES_DIR=str(bundle_root / 'build_inputs/tables'), KOSIS_API_KEY='')
    api_log = (run_dir / 'api.log').open('w', encoding='utf-8')
    web_log = (run_dir / 'web.log').open('w', encoding='utf-8')
    processes = []
    profile = json.loads((bundle_root / 'profiles.json').read_text(encoding='utf-8'))['baseline']
    effective_model = apply_profile(env, profile)
    result = {'case_id': case['id'], 'status': 'not_executed', 'product_revision': '',
              'profile': profile, 'effective_model': effective_model,
              'bundle_manifest_sha256': hashlib.sha256((bundle_root / 'manifest.json').read_bytes()).hexdigest(),
              'adapter_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'reason': 'browser run did not complete'}
    api_responses = []
    try:
        revision = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=product_root, check=True,
                                  capture_output=True, text=True).stdout.strip()
        result['product_revision'] = revision
        processes.append(subprocess.Popen([str(product_python), '-m', 'uvicorn', 'bridge_api:app',
                            '--host', '127.0.0.1', '--port', str(api_port)], cwd=product_root, env=env,
                            stdout=api_log, stderr=subprocess.STDOUT))
        processes.append(subprocess.Popen(['pnpm', 'dev', '--host', '127.0.0.1', '--port', str(web_port)],
                            cwd=product_root / 'src/agent/frontend', env=env,
                            stdout=web_log, stderr=subprocess.STDOUT))
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(accept_downloads=True)
            def capture(response):
                if '/api/query' in response.url or '/api/output' in response.url:
                    try:
                        api_responses.append(response.json())
                    except Exception:
                        pass
            page.on('response', capture)
            base = f'http://127.0.0.1:{web_port}'
            for _ in range(60):
                try:
                    page.goto(base, wait_until='domcontentloaded', timeout=3000)
                    break
                except Exception:
                    time.sleep(.5)
            page.get_by_label('로그인 아이디').fill(username)
            page.get_by_label('로그인 비밀번호').fill(password)
            page.get_by_role('button', name='로그인하기').click()
            page.get_by_label('통계 질문').fill(case['input']['query'])
            page.get_by_role('button', name='분석하기').click()
            page.locator('#analysis-result').wait_for(timeout=180000)
            if page.get_by_role('button', name='데이터 조회').count():
                if not case['expected'].get('series_contracts'):
                    raise RuntimeError('blocked case cannot be executed')
                start = case['expected']['series_contracts'][0]['periods'][0]
                end = case['expected']['series_contracts'][0]['periods'][-1]
                from datetime import date
                def ui_date(value, frequency, end_of_period=False):
                    if frequency == 'M':
                        year, month = int(value[:4]), int(value[4:])
                    elif frequency == 'Q':
                        year, quarter = int(value[:4]), int(value[-1])
                        month = quarter * 3 if end_of_period else quarter * 3 - 2
                    else:
                        year, month = int(value), 12 if end_of_period else 1
                    day = 1 if not end_of_period else __import__('calendar').monthrange(year, month)[1]
                    return date(year, month, day).isoformat()
                for label, value, is_end in (('시작일', start, False), ('종료일', end, True)):
                    page.get_by_role('button', name=f'{label} 선택').click()
                    fields = page.locator('.date-select-grid select')
                    day = ui_date(value, case['expected']['series_contracts'][0]['frequency'], is_end)
                    year, month, date_no = day.split('-')
                    fields.nth(0).select_option(label=year + '년')
                    fields.nth(1).select_option(label=str(int(month)) + '월')
                    fields.nth(2).select_option(label=str(int(date_no)) + '일')
                    page.get_by_role('button', name='이 날짜로 선택').click()
                page.get_by_role('button', name='데이터 조회').click()
                page.locator('#analysis-result').wait_for(timeout=180000)
            if page.get_by_role('button', name='그래프 생성').count():
                page.get_by_role('button', name='그래프 생성').click()
            page.locator('.chart-workspace').wait_for(timeout=180000)
            data = next((value for value in reversed(api_responses) if value.get('chart')), None)
            if data is None:
                raise RuntimeError('no rendered chart series in product API response')
            observed = {'series': observed_series(data['chart'], case['expected']['series_contracts'])}
            page.screenshot(path=str(run_dir / 'output.png'), full_page=True)
            observed.update(ui_output_visible=True, output_kind=case['expected']['output_kind'])
            if case['expected']['output_kind'] == 'table':
                page.get_by_role('button', name='표', exact=True).last.click()
                page.get_by_text('파일 내보내기', exact=True).click()
                with page.expect_download(timeout=30000) as download_info:
                    page.get_by_role('button', name='XLSX 다운로드').click()
                download = download_info.value
                downloaded = run_dir / 'observed.xlsx'
                download.save_as(downloaded)
                observed['xlsx_cells'] = read_xlsx_cells(downloaded)
                observed['xlsx_downloaded'] = True
            (run_dir / 'observed.json').write_text(json.dumps(observed, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            result.update(status='observed', reason=None,
                          ui_output_visible=True, xlsx_checked=case['expected']['output_kind'] == 'table')
            (run_dir / 'page.txt').write_text(page.locator('body').inner_text(), encoding='utf-8')
            browser.close()
    except Exception as exc:
        result.update(status='fail', reason=f'{type(exc).__name__}: {exc}')
    finally:
        for process in processes:
            process.terminate()
        for process in processes:
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        api_log.close()
        web_log.close()
    (run_dir / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--product-root', required=True)
    parser.add_argument('--bundle-root', required=True, help='Extracted evaluation ZIP root')
    parser.add_argument('--case-id', required=True)
    parser.add_argument('--run-dir', required=True)
    parser.add_argument('--username', default=os.getenv('STATBRIDGE_EVAL_USERNAME', 'test1'))
    parser.add_argument('--password', default=os.getenv('STATBRIDGE_EVAL_PASSWORD', '1234'))
    args = parser.parse_args()
    bundle_root = Path(args.bundle_root)
    cases = [json.loads(line) for line in (bundle_root / 'cases.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
    case = next((value for value in cases if value['id'] == args.case_id), None)
    if case is None:
        raise SystemExit('unknown case id')
    if case['status'] != 'runnable':
        raise SystemExit('blocked cases cannot be executed')
    print(json.dumps(run_case(args.product_root, bundle_root, case, args.run_dir,
                              args.username, args.password), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
