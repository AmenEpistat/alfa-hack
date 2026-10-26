"""Separate opt-in ASGI entry point, with no effect on app.main:app."""
import os
from pathlib import Path

if os.environ.get('ALPHA_SYNTHETIC_DEMO') != '1':
    raise RuntimeError('Use the dedicated synthetic Compose file to enable this test stand')

from fastapi.responses import JSONResponse
from app.main import app
from app.routers import agent, pipeline
from demo.runtime import FixtureClient, handle_request, settings

pipeline.handle_request = handle_request
agent.JsonLLMClient = FixtureClient
agent._settings = settings
if os.environ.get('ALPHA_SYNTHETIC_WORKDIR'):
    work = Path(os.environ['ALPHA_SYNTHETIC_WORKDIR'])
    agent.CACHE_ROOT = work / 'cache'
    agent.INSIGHT_OUTPUT_ROOT = work / 'chat'


@app.middleware('http')
async def synthetic_boundary(request, call_next):
    if request.url.path == '/api/insight-agent/health':
        return JSONResponse({'status': 'synthetic', 'llm_configured': False, 'mode': 'synthetic'})
    if request.url.path in {'/api/parser/collect', '/api/parser/pdf', '/api/ranking/run', '/api/insight-agent/generate'}:
        return JSONResponse({'detail': 'Use /api/pipeline/run on the synthetic stand'}, status_code=409)
    response = await call_next(request)
    response.headers['X-Alpha-Mode'] = 'synthetic'
    return response


@app.get('/api/demo/status')
def demo_status():
    return {'mode': 'synthetic', 'company_id': 'U_900001',
            'simulated': ['source collection and PDF extraction', 'neural ranking', 'LLM and chat'],
            'real': ['CSV preprocessing', 'pipeline orchestration', 'citation validation',
                     'Markdown export', 'publication', 'SQLite', 'authentication', 'preferences']}
