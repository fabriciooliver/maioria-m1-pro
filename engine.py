from datetime import datetime, timezone
from math import sqrt

def analyze(candles, payout=86, stake=10):
    data={}
    for c in candles:
        try:
            t=int(c.get('from',c.get('timestamp')))
            if t%60: continue
            o=float(c['open']); cl=float(c['close'])
            data[t]=1 if cl>o else -1 if cl<o else 0
        except (ValueError,TypeError,KeyError): continue
    times=sorted(data); cycles=[]; p=payout/100
    for t in times:
        if (t//60)%5: continue
        prior=[t-60*i for i in range(5,0,-1)]
        nxt=[t+60*i for i in range(3)]
        if not all(x in data for x in prior+nxt): continue
        v=[data[x] for x in prior]
        if 0 in v: continue
        direction=1 if sum(v)>0 else -1
        outcome=next((i for i,x in enumerate(nxt) if data[x]==direction),3)
        s0=stake; s1=s0*(1+p)/p; s2=(s0+s1+s0*p)/p
        stakes=[s0,s1,s2]
        pnl=-sum(stakes) if outcome==3 else -sum(stakes[:outcome])+stakes[outcome]*p
        cycles.append({'time':datetime.fromtimestamp(t,timezone.utc).isoformat(),'signal':'CALL' if direction==1 else 'PUT','outcome':['WIN','MG1','MG2','LOSS'][outcome], 'pnl':round(pnl,2)})
    n=len(cycles); loss=sum(c['outcome']=='LOSS' for c in cycles)
    last_loss = next(
    (
        datetime.fromtimestamp(
    datetime.fromisoformat(c['time']).timestamp() + 180,
    timezone.utc
).isoformat()
        for c in reversed(cycles)
        if c['outcome'] == 'LOSS'
    ),
    None
)
    wins=n-loss
    # Wilson 95% interval for observed win rate
    if n:
        z=1.96; ph=wins/n; den=1+z*z/n
        mid=(ph+z*z/(2*n))/den
        half=z*sqrt(ph*(1-ph)/n+z*z/(4*n*n))/den
        interval=[round(100*(mid-half),2),round(100*(mid+half),2)]
    else: interval=[0,0]
    return {'cycles':n,'direct':sum(c['outcome']=='WIN' for c in cycles),'mg1':sum(c['outcome']=='MG1' for c in cycles),'mg2':sum(c['outcome']=='MG2' for c in cycles),'loss':loss,'win_rate':round(100*wins/n,2) if n else 0,'ci95':interval,'pnl':round(sum(c['pnl'] for c in cycles),2),'last_loss': last_loss,
'operations': cycles[-150:]}
