# osu MP Link Miner

CLI em Python que recebe um nickname e procura partidas multiplayer publicas que
contenham o jogador. O nickname e resolvido para o ID permanente da conta.

## Configuracao

Requer Python 3.10+ e uma aplicacao OAuth criada nas configuracoes do osu.
O programa usa Client Credentials com escopo public.

No PowerShell:

```powershell
$env:OSU_CLIENT_ID = "SEU_CLIENT_ID"
$env:OSU_CLIENT_SECRET = "SEU_CLIENT_SECRET"
cd C:\Users\Felipe\osu_mp_miner
.\.venv\Scripts\python.exe .\mp_miner.py "Nickname"
```

Exemplos:

```powershell
# Examina ate 1.000 partidas recentes
.\.venv\Scripts\python.exe .\mp_miner.py "Nickname" --pages 20

# Para em uma data e salva somente links
.\.venv\Scripts\python.exe .\mp_miner.py "Nickname" --pages 100 --since 2026-08-01 --format txt
```

Formatos disponiveis: JSON, CSV e TXT.

## Limitacao

A API v2 nao oferece busca de partida por jogador. O programa percorre a listagem
global, da partida mais recente para a mais antiga, e verifica os participantes.
Por isso, aumentar --pages amplia o alcance, mas faz mais requisicoes.

## Testes

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```
