import time

def connect(email,password):
    try:
        from iqoptionapi.stable_api import IQ_Option
    except ImportError as e:
        raise RuntimeError('Dependência iqoptionapi ausente; instale o adaptador comunitário no servidor.') from e
    api=IQ_Option(email,password)
    ok, reason=api.connect()
    if not ok: raise RuntimeError(f'Falha de autenticação/conexão: {str(reason)[:150]}')
    api.change_balance('PRACTICE')
    return api

def pairs(api,kind):
    raw=api.get_all_open_time() or {}
    return sorted(k for k,v in raw.get(kind,{}).items() if isinstance(v,dict) and v.get('open'))

def candles(api,pair,count):
    end=int(time.time()//60*60)-1
    result={}
    for _ in range((count+999)//1000):
        batch=api.get_candles(pair,60,min(1000,count-len(result)),end)
        if not batch: break
        for x in batch: result[int(x['from'])]=x
        earliest=min(int(x['from']) for x in batch)
        if earliest>=end: break
        end=earliest-1
        time.sleep(.12)
    return sorted(result.values(),key=lambda x:int(x['from']))[-count:]
