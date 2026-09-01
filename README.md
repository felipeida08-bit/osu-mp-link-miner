# osu MP Link Miner

CLI e interface grafica em Python para procurar partidas multiplayer publicas que
contenham um jogador. O nickname e resolvido para o ID permanente da conta.

## Configuracao

Requer Python 3.10+ e uma aplicacao OAuth criada nas configuracoes do osu.
O programa usa Client Credentials com escopo public.

No PowerShell:

```powershell
$env:OSU_CLIENT_ID = "SEU_CLIENT_ID"
$env:OSU_CLIENT_SECRET = "SEU_CLIENT_SECRET"
cd C:\Users\Felipe\osu_mp_miner
```

## Interface grafica

```powershell
.\.venv\Scripts\python.exe .\gui.py
```

A busca da interface funciona como uma fila:

- recebe paginas da API em ordem decrescente de MP ID;
- verifica ate 5 partidas em paralelo por padrao;
- continua indefinidamente quando o limite de paginas e zero;
- para e salva os resultados quando o usuario clica em **Parar**;
- exibe pagina, partidas verificadas, encontradas e MP ID atual;
- renova automaticamente o token OAuth em execucoes longas.

O campo **Verificar um MP diretamente** aceita um ID ou um link completo, por
exemplo `https://osu.ppy.sh/community/matches/121788519`.

Formatos de saida disponiveis: JSON, CSV e TXT. Um duplo clique abre o MP link.

## Linha de comando

```powershell
# Examina ate 1.000 partidas recentes
.\.venv\Scripts\python.exe .\mp_miner.py "Nickname" --pages 20

# Para em uma data e salva somente links
.\.venv\Scripts\python.exe .\mp_miner.py "Nickname" --pages 100 --since 2026-08-01 --format txt
```

## Limitacao

A API v2 nao oferece busca de partida legada por jogador. O programa percorre a
listagem global, da partida mais recente para a mais antiga, e verifica os
participantes. As salas modernas do osu lazer usam outro sistema (`/rooms`) e
ainda nao fazem parte desta busca.

## Testes

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```
