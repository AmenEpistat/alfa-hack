"""Run the acceptance scenario without sockets; isolate all mutable data in a temp directory."""
import os
import tempfile


def main():
    with tempfile.TemporaryDirectory(prefix='alfa-synthetic-check-') as work:
        os.environ['ALPHA_SYNTHETIC_DEMO'] = '1'
        os.environ['ALPHA_SYNTHETIC_WORKDIR'] = work
        os.environ['DATABASE_URL'] = f'sqlite:///{work}/backend.db'
        from fastapi.testclient import TestClient
        from demo.app import app
        from demo.verify import verify
        # Keep this entry point in its own process: demo.app deliberately replaces ML boundaries.
        with TestClient(app) as client:
            verify('http://testserver', client=client)
            first = client.get('/api/insights', headers={'Authorization': 'Bearer anna'}).json()
        with TestClient(app) as client:
            verify('http://testserver', client=client)
            second = client.get('/api/insights', headers={'Authorization': 'Bearer anna'}).json()
            assert {i['id'] for i in first} == {i['id'] for i in second}, 'Replay must not duplicate articles'
            assert client.get('/api/insight-agent/health').json()['llm_configured'] is False
            assert client.post('/api/parser/collect', json={}).status_code == 409
            assert client.post('/api/pipeline/run', headers={'Authorization': 'Bearer anna'},
                               json={'audience_type': 'cfo', 'company_id': 'U_1'}).status_code == 422
        print('PASS restart, persistence, replay deduplication and synthetic boundary checks')


if __name__ == '__main__':
    main()
