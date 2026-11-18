# MAIORIA M1 PRO — Site para PC

Site com FastAPI, coleta periódica no servidor e ranking de pares da IQ Option.

## Atenção
- Não é um site já hospedado: precisa de implantação em um servidor com processo Python persistente (Render/Railway/VPS). GitHub Pages sozinho NÃO executa o backend.
- A IQ Option não oferece uma API pública oficial validada para este projeto. `iqoptionapi` é comunitária, pode quebrar, ter problemas de instalação ou não ser autorizada para seu uso. Verifique as condições da plataforma.
- Não envie senha por chat, não exponha `.env`, não configure credenciais no frontend. Use secrets no provedor de hospedagem e HTTPS. Proteja o painel com autenticação/restrição de acesso antes de disponibilizar publicamente.
- Nenhuma ordem é enviada. A sessão é configurada para PRACTICE.

## Execução local
1. Python 3.11 instalado.
2. `pip install -r requirements.txt`
3. Instale uma versão compatível da biblioteca comunitária `iqoptionapi` separadamente, seguindo as instruções do repositório que você escolher e verificando a procedência. Não há pacote oficial validado neste projeto.
4. Configure variáveis de ambiente de `.env.example` no sistema (o arquivo `.env` não é carregado automaticamente).
5. `uvicorn server:app --host 127.0.0.1 --port 8000`
6. Abra `http://127.0.0.1:8000` no PC.

## Hospedagem
- Crie repositório privado com os arquivos.
- Hospede como **Web Service** Python ou Docker em Render, Railway ou VPS; habilite HTTPS.
- Defina `IQ_EMAIL`, `IQ_PASSWORD` como secrets do serviço; demais variáveis conforme `.env.example`.
- Configure instalação do adaptador comunitário no build da sua hospedagem, após revisar a biblioteca.
- O serviço deve ficar ligado para a coleta recorrente. Em planos gratuitos com suspensão, a atualização não é contínua.
- Rode somente **uma instância/worker**, pois cada instância criará sua própria thread de coleta. Para escala, use um agendador externo e banco de dados.
- Restrinja o acesso ao painel; o exemplo não inclui login.

## Metodologia
Blocos de 5 minutos alinhados em UTC. Maioria das 5 velas fechadas anteriores, sinal na primeira vela do bloco seguinte, MG1 na segunda, MG2 na terceira. Empates de preço tratados como perda. Dojis na amostra de maioria e candles ausentes descartam ciclo. Payout configurado é fixo e não reflete a série histórica. IC 95% de Wilson é incerteza amostral aproximada, não probabilidade futura. Resultados sobrepostos e não-estacionariedade podem invalidar inferência estatística. Nenhuma execução de ordem.
