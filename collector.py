import re
import time

# Apenas pares de moedas fiduciarias. Inclui pares OTC.
CURRENCIES = frozenset({
    'AUD', 'CAD', 'CHF', 'EUR', 'GBP', 'JPY', 'NZD', 'USD',
    'BRL', 'MXN', 'TRY', 'ZAR', 'NOK', 'SEK', 'DKK', 'PLN',
    'SGD', 'HKD', 'CNH', 'CNY', 'INR', 'RUB', 'THB', 'ILS',
})
PAIR_PATTERN = re.compile(r'^([A-Z]{3})/?([A-Z]{3})(?:-OTC)?$')


def is_forex_pair(name):
    if not isinstance(name, str):
        return False
    match = PAIR_PATTERN.fullmatch(name.upper())
    return bool(
        match and match.group(1) != match.group(2)
        and match.group(1) in CURRENCIES
        and match.group(2) in CURRENCIES
    )


def connect(email, password):
    try:
        from iqoptionapi.stable_api import IQ_Option
    except ImportError as exc:
        raise RuntimeError('Dependencia iqoptionapi ausente no servidor.') from exc

    api = IQ_Option(email, password)
    ok, reason = api.connect()
    if not ok:
        raise RuntimeError(f'Falha de conexao: {str(reason)[:150]}')
    api.change_balance('PRACTICE')
    return api


def pairs(api, kind, min_payout=86):
    # min_payout permanece apenas por compatibilidade com server.py.
    # Nao excluimos pares pelo payout informado pela API.
    if kind not in ('turbo', 'binary'):
        raise ValueError('Tipo de mercado nao suportado')

    print('ETAPA 3: Consultando pares Forex sem filtro de payout...', flush=True)
    profits = api.get_all_profit()
    if not isinstance(profits, dict):
        raise RuntimeError('Resposta invalida ao consultar ativos')

    selected = []
    for name, info in profits.items():
        if not is_forex_pair(name) or not isinstance(info, dict):
            continue
        # Exige que o ativo esteja listado para o mercado binario escolhido,
        # mas nao exige um retorno minimo.
        raw = info.get(kind)
        if raw is None or isinstance(raw, bool):
            continue
        try:
            payout = float(raw)
        except (TypeError, ValueError):
            continue
        if not (0 < payout <= 100):
            continue
        if payout <= 1:
            payout *= 100
        selected.append((name, payout))

    # Ordenacao apenas informativa; nenhum payout minimo e aplicado.
    selected.sort(key=lambda item: (-item[1], item[0]))
    print(f'ETAPA 4: {len(selected)} pares Forex identificados sem payout minimo.', flush=True)
    print('PARES FOREX (amostra):', selected[:15], flush=True)
    return [name for name, _ in selected]


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
