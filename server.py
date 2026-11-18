import os,threading,time
from datetime import datetime,timezone
from fastapi import FastAPI,HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from engine import analyze
from collector import connect,pairs,candles

app=FastAPI(title='Maioria M1 Pro')
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

STATIC_DIR.mkdir(parents=True, exist_ok=True)

app.mount(
    "/static",
    StaticFiles(directory=str(STATIC_DIR)),
    name="static"
)
lock=threading.Lock()
state={'status':'aguardando','updated_at':None,'rows':[],'errors':[],'scan_count':0}
CONFIG={'kind':os.getenv('IQ_MARKET','turbo'),'max_pairs':max(1,min(50,int(os.getenv('MAX_PAIRS','15')))),'candles':max(100,min(10000,int(os.getenv('CANDLES_PER_PAIR','2000')))),'payout':float(os.getenv('PAYOUT','86')),'stake':float(os.getenv('STAKE','10')),'interval':max(120,int(os.getenv('SCAN_INTERVAL_SECONDS','300')))}

def scan():
    email=os.getenv('IQ_EMAIL'); password=os.getenv('IQ_PASSWORD')
    if not email or not password:
        with lock: state.update(status='configuração pendente',errors=['Configure IQ_EMAIL e IQ_PASSWORD nas variáveis secretas do servidor.'])
        return
    with lock: state['status']='analisando'
    api=None; rows=[]; errors=[]
    try:
        
        print("ETAPA 1: Conectando à IQ Option...", flush=True)
        api = connect(email, password)

        print("ETAPA 2: Conexão realizada.", flush=True)
        print("ETAPA 3: Buscando pares disponíveis...", flush=True)

        available = pairs(api, CONFIG['kind'])[:CONFIG['max_pairs']]

        print(f"ETAPA 4: {len(available)} pares encontrados.", flush=True)

        if not available: errors.append('Nenhum par aberto retornado pela plataforma.')
        for pair in available:
            try:
                result=analyze(candles(api,pair,CONFIG['candles']),CONFIG['payout'],CONFIG['stake'])
                rows.append({'pair':pair,**result})
            except Exception as e: errors.append(f'{pair}: {str(e)[:180]}')
    except Exception as e: errors.append(str(e)[:250])
    finally:
        if api:
            try: api.close_connect()
            except Exception: pass
    rows.sort(key=lambda r:(r['ci95'][0] if r['cycles']>=30 else -1,r['pnl']),reverse=True)
    with lock:
        state.update(status='concluído' if rows else 'erro',updated_at=datetime.now(timezone.utc).isoformat(),rows=rows,errors=errors,scan_count=state['scan_count']+1)

def loop():
    while True:
        scan(); time.sleep(CONFIG['interval'])

@app.on_event('startup')
def start():
    threading.Thread(target=loop,daemon=True).start()

@app.get('/')
def home(): return FileResponse('static/index.html')

@app.get('/api/status')
def status():
    with lock: return {'state':dict(state),'config':{k:v for k,v in CONFIG.items() if k not in ('stake',)}}

@app.get('/api/health')
def health(): return {'ok':True}
import sys

@app.get("/api/python-version")
def python_version():
    return {"python_version": sys.version}
