"""Run against the actual HTTP API (and nginx when using Compose). No pytest needed."""
import argparse
import json
import urllib.request
from urllib.error import HTTPError
from pathlib import Path


def verify(base_url, *, client=None):
    def request(path, body=None, token=None, expected=200):
        headers = {'Content-Type': 'application/json'}
        if token:
            headers['Authorization'] = 'Bearer ' + token
        if client is not None:
            response = client.request('GET' if body is None else 'POST', path, json=body, headers=headers)
            if response.status_code != expected:
                raise RuntimeError(f'{path}: expected {expected}, got {response.status_code}: {response.text[:2000]}')
            return response.json()
        req = urllib.request.Request(base_url.rstrip('/') + path,
                                     data=None if body is None else json.dumps(body).encode(), headers=headers)
        try:
            response = urllib.request.urlopen(req, timeout=120)
        except HTTPError as exc:
            response = exc
        with response:
            content = response.read().decode()
            if response.status != expected:
                raise RuntimeError(f'{path}: expected {expected}, got {response.status}: {content[:2000]}')
            return json.loads(content)

    if request('/api/demo/status').get('mode') != 'synthetic':
        raise RuntimeError('Refusing to write test data into a non-synthetic API')
    request('/api/insights', expected=401)
    published = {}
    for user, role in [('anna', 'cfo'), ('ilya', 'treasury_head')]:
        token = request('/api/auth/login', {'user_id': user})['access_token']
        payload = json.loads((Path(__file__).parent / 'fixtures' / f'request-{user}.json').read_text())
        response = request('/api/pipeline/run', payload, token)
        ids = response.get('published_insight_ids', [])
        if response['status'] != 'completed' or len(ids) != 5:
            raise RuntimeError(f'{user}: expected five completed insights: {json.dumps(response, ensure_ascii=False)[:4000]}')
        published[user] = set(ids)
        feed = request('/api/insights', token=token)
        assert set(ids) <= {item['id'] for item in feed}
        assert all(item['audience_type'] == role for item in feed)
        item = request('/api/insights/' + ids[0], token=token)
        assert 'СИНТЕТИЧЕСКИЙ' in item['title'] and item['content']
        sources = request('/api/insights/' + ids[0] + '/sources', token=token)
        assert len(sources) >= 2
        saved = request('/api/preferences/' + ids[0] + '/toggle', {}, token)
        assert request('/api/insights/' + ids[0], token=token)['is_saved'] == saved['is_saved']
        request('/api/preferences/' + ids[0] + '/toggle', {}, token)
        answer = request('/api/insights/ask', {'insight_id': ids[0], 'question': 'Что проверить?', 'history': []}, token)
        assert answer['paragraphs'] and 'СИНТЕТИЧЕСКИЙ ОТВЕТ' in answer['paragraphs'][0]
        assert answer['references']
        wrong_role = 'treasury_head' if role == 'cfo' else 'cfo'
        request('/api/pipeline/run', {**payload, 'audience_type': wrong_role}, token, expected=403)
        print(f'PASS {user}: preprocessing → pipeline → 5 validated articles → feed → sources → save → chat')
    assert published['anna'].isdisjoint(published['ilya'])
    transport = 'ASGI integration' if client is not None else 'HTTP E2E'
    print(f'PASS synthetic {transport}. Source collection, neural ranking and LLM were simulated.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='http://127.0.0.1:8081')
    verify(parser.parse_args().base_url)
