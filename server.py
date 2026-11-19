import os
import sys
import threading
import time
import logging
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

CONFIG = {
    'kind': os.getenv('IQ_MARKET', 'turbo'),
    'max_pairs': max(1, min(50, int(os.getenv('MAX_PAIRS', '15')))),
    'max_candidates': max(1, min(100, int(os.getenv('MAX_CANDIDATES', '35')))),
    'min_cycles': max(1, int(os.getenv('MIN_CYCLES', '30'))),
    'candles': max(100, min(10000, int(os.getenv('CANDLES_PER_PAIR', '2000')))),
    'payout': float(os.getenv('PAYOUT', '86')),
    'stake': float(os.getenv('STAKE', '10')),
    'interval': max(60, int(os.getenv('SCAN_INTERVAL_SECONDS', '60'))),
}

lock = threading.Lock()
state = {
    'status': 'aguardando', 'updated_at': None,
    'rows': [], 'errors': [], 'scan_count': 0,
}


def scan():
    email = os.getenv('IQ_EMAIL')
    password = os.getenv('IQ_PASSWORD')
    if not email or not password:
        with lock:
            state.update(status='configuração pendente', errors=[
                'Configure IQ_EMAIL e IQ_PASSWORD nas variáveis secretas do Render.'
            ])
        return

    with lock:
        state['status'] = 'analisando'

    api = None
    valid_rows = []
    errors = []
    try:
        print('ETAPA 1: Conectando à IQ Option...', flush=True)
        api = connect(email, password)
        print('ETAPA 2: Conexão realizada.', flush=True)
        available = pairs(api, CONFIG['kind'], CONFIG['payout'])
        candidates = available[:CONFIG['max_candidates']]
        print(f'ETAPA 5: Testando histórico de {len(candidates)} candidatos.', flush=True)
        if not candidates:
            errors.append('Nenhum candidato retornado pelo filtro de payout; abertura não verificada.')

        for pair in candidates:
            try:
                history = candles(api, pair, CONFIG['candles'])
                if not history:
                    print(f'IGNORADO {pair}: sem velas.', flush=True)
                    continue
                result = analyze(history, CONFIG['payout'], CONFIG['stake'])
                if result['cycles'] < CONFIG['min_cycles']:
                    print(f"IGNORADO {pair}: {result['cycles']} ciclos.", flush=True)
                    continue
                valid_rows.append({'pair': pair, **result})
                print(f"VALIDO {pair}: {result['cycles']} ciclos.", flush=True)
            except Exception as exc:
                msg = f'{pair}: {str(exc)[:180]}'
                errors.append(msg)
                print(f'ERRO {msg}', flush=True)
    except Exception as exc:
        errors.append(f'Falha na coleta: {str(exc)[:250]}')
        logging.exception('Falha geral na coleta')
    finally:
        if api is not None:
            try:
                websocket = getattr(api, 'websocket', None)
                if websocket is not None:
                    close = getattr(websocket, 'close', None)
                    if callable(close):
                        close()
            except Exception:
                logging.exception('Falha ao encerrar conexão')

    valid_rows.sort(key=lambda r: (r['ci95'][0], r['pnl']), reverse=True)
    top = valid_rows[:CONFIG['max_pairs']]
    print(f'ETAPA 6: {len(top)} pares válidos no ranking.', flush=True)

    with lock:
        state['scan_count'] += 1
        state['errors'] = errors[-40:]
        if top:
            state.update(status='concluído', updated_at=datetime.now(timezone.utc).isoformat(), rows=top)
        else:
            state['status'] = 'sem novos resultados' if state['rows'] else 'erro'
            if not errors:
                state['errors'] = ['Nenhum ativo com histórico suficiente nesta coleta.']


def loop():
    # Agenda a próxima coleta a partir do início da anterior, evitando sobreposição.
    # A coleta de 35 ativos/2000 velas pode demorar mais que um minuto.
    while True:
        started = time.monotonic()
        try:
            scan()
        except Exception:
            logging.exception('Erro inesperado no ciclo de análise')
            with lock:
                state['status'] = 'erro'
        elapsed = time.monotonic() - started
        time.sleep(max(1, CONFIG['interval'] - elapsed))


@app.on_event('startup')
def start():
    threading.Thread(target=loop, daemon=True).start()


@app.get('/')
def home():
    return FileResponse(STATIC_DIR / 'index.html')


@app.get('/api/status')
def status():
    with lock:
        snapshot = {**state, 'rows': list(state['rows']), 'errors': list(state['errors'])}
    return {'state': snapshot, 'config': {k: v for k, v in CONFIG.items() if k != 'stake'}}


@app.get('/api/health')
def health():
    return {'ok': True}


@app.get('/api/python-version')
def python_version():
    return {'python_version': sys.version}
