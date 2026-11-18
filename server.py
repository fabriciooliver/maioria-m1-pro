import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from collector import connect, pairs, candles
from engine import analyze

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / 'static'
STATIC_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title='Maioria M1 Pro')
app.mount('/static', StaticFiles(directory=str(STATIC_DIR)), name='static')

lock = threading.Lock()
state = {
    'status': 'aguardando',
    'updated_at': None,
    'rows': [],
    'errors': [],
    'scan_count': 0,
}

CONFIG = {
    'kind': os.getenv('IQ_MARKET', 'turbo'),
    'max_pairs': max(1, min(50, int(os.getenv('MAX_PAIRS', '15')))),
    'candidates': max(1, min(100, int(os.getenv('SCAN_CANDIDATES', '35')))),
    'min_cycles': max(1, int(os.getenv('MIN_CYCLES', '30'))),
    'candles': max(100, min(10000, int(os.getenv('CANDLES_PER_PAIR', '2000')))),
    'payout': float(os.getenv('PAYOUT', '86')),
    'stake': float(os.getenv('STAKE', '10')),
    'interval': max(120, int(os.getenv('SCAN_INTERVAL_SECONDS', '300'))),
}


def scan():
    email = os.getenv('IQ_EMAIL')
    password = os.getenv('IQ_PASSWORD')
    if not email or not password:
        with lock:
            state.update(
                status='configuração pendente',
                errors=['Configure IQ_EMAIL e IQ_PASSWORD nas variáveis secretas do Render.'],
            )
        return

    with lock:
        state['status'] = 'analisando'

    api = None
    rows = []
    errors = []
    try:
        print('ETAPA 1: Conectando à IQ Option...', flush=True)
        api = connect(email, password)
        print('ETAPA 2: Conexão realizada.', flush=True)

        # pairs() já ordena os candidatos por payout informado.
        available = pairs(api, CONFIG['kind'], CONFIG['payout'])
        candidates = available[:max(CONFIG['candidates'], CONFIG['max_pairs'])]
        print(f'ETAPA 5: Testando histórico de {len(candidates)} candidatos.', flush=True)

        if not candidates:
            errors.append('Nenhum ativo retornou payout informado acima do mínimo configurado.')

        for index, pair in enumerate(candidates, start=1):
            try:
                history = candles(api, pair, CONFIG['candles'])
                if len(history) < 10:
                    print(f'Ignorando {pair}: apenas {len(history)} velas.', flush=True)
                    continue

                result = analyze(history, CONFIG['payout'], CONFIG['stake'])
                if result['cycles'] < CONFIG['min_cycles']:
                    print(f'Ignorando {pair}: {result["cycles"]} ciclos.', flush=True)
                    continue

                rows.append({'pair': pair, **result})
                print(f'[{index}/{len(candidates)}] {pair}: {result["cycles"]} ciclos.', flush=True)
            except Exception as exc:
                # Ativos desconhecidos na versão instalada da biblioteca não bloqueiam o scan.
                message = f'{pair}: {type(exc).__name__}: {str(exc)[:140]}'
                errors.append(message)
                print('Falha no ativo: ' + message, flush=True)

    except Exception as exc:
        message = f'{type(exc).__name__}: {str(exc)[:220]}'
        errors.append(message)
        print('Falha na coleta: ' + message, flush=True)
    finally:
        if api is not None:
            try:
                api.close_connect()
            except Exception:
                pass

    # Critério: limite inferior de Wilson 95%; desempate pelo PnL simulado.
    rows.sort(key=lambda r: (r['ci95'][0], r['pnl']), reverse=True)
    top = rows[:CONFIG['max_pairs']]

    with lock:
        state['scan_count'] += 1
        state['updated_at'] = datetime.now(timezone.utc).isoformat()
        state['errors'] = errors[-50:]
        if top:
            state['rows'] = top
            state['status'] = 'concluído'
        else:
            # Não apaga o último ranking válido em caso de falha.
            state['status'] = 'erro' if not state['rows'] else 'dados anteriores'
            if not errors:
                state['errors'] = ['Nenhum candidato atingiu o mínimo de ciclos nesta coleta.']

    print(f'ETAPA 6: {len(top)} pares válidos no ranking.', flush=True)


def loop():
    while True:
        scan()
        time.sleep(CONFIG['interval'])


@app.on_event('startup')
def start():
    threading.Thread(target=loop, daemon=True).start()


@app.get('/')
def home():
    return FileResponse(STATIC_DIR / 'index.html')


@app.get('/api/status')
def status():
    with lock:
        return {
            'state': {
                **state,
                'rows': list(state['rows']),
                'errors': list(state['errors']),
            },
            'config': {k: v for k, v in CONFIG.items() if k != 'stake'},
        }


@app.get('/api/health')
def health():
    return {'ok': True}


@app.get('/api/python-version')
def python_version():
    import sys
    return {'python_version': sys.version}
