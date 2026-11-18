import time


def connect(email, password):
    try:
        from iqoptionapi.stable_api import IQ_Option
    except ImportError as exc:
        raise RuntimeError('Dependência iqoptionapi ausente no servidor.') from exc

    api = IQ_Option(email, password)
    ok, reason = api.connect()
    if not ok:
        raise RuntimeError(f'Falha de autenticação/conexão: {str(reason)[:150]}')
    api.change_balance('PRACTICE')
    return api



def pairs(api, kind, min_payout=86):
    if kind not in ("turbo", "binary"):
        raise ValueError("Tipo de mercado não suportado")

    print("ETAPA 3: Consultando ativos e payout...", flush=True)

    profits = api.get_all_profit()

    if not isinstance(profits, dict):
        raise RuntimeError("Resposta inválida ao consultar payouts")

    selected = []

    for name, info in profits.items():
        if not isinstance(info, dict):
            continue

        raw = info.get(kind)

        if raw is None or isinstance(raw, bool):
            continue

        try:
            payout = float(raw)
        except (TypeError, ValueError):
            continue

        if 0 < payout <= 1:
            payout *= 100

        if min_payout <= payout <= 100:
            selected.append((name, payout))

    selected.sort(key=lambda item: (-item[1], item[0]))

    print(
        f"ETAPA 4: {len(selected)} ativos com payout >= {min_payout}%.",
        flush=True
    )

    return [name for name, payout in selected]



def candles(api, pair, count):
    count = int(count)
    if count <= 0:
        return []

    end = (int(time.time()) // 60) * 60 - 1
    result = {}
    while len(result) < count:
        batch_size = min(1000, count - len(result))
        batch = api.get_candles(pair, 60, batch_size, end)
        if not batch:
            break
        earliest = None
        for candle in batch:
            try:
                timestamp = int(candle['from'])
            except (KeyError, TypeError, ValueError):
                continue
            if timestamp <= end and timestamp % 60 == 0:
                result[timestamp] = candle
                earliest = timestamp if earliest is None else min(earliest, timestamp)
        if earliest is None or earliest > end:
            break
        next_end = earliest - 1
        if next_end >= end:
            break
        end = next_end
        time.sleep(0.12)
    return [result[t] for t in sorted(result)][-count:]
