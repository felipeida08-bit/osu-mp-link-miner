# osu! MP Link Miner

[![Tests](https://github.com/felipeida08-bit/osu-mp-link-miner/actions/workflows/tests.yml/badge.svg)](https://github.com/felipeida08-bit/osu-mp-link-miner/actions/workflows/tests.yml)
[![Build Windows](https://github.com/felipeida08-bit/osu-mp-link-miner/actions/workflows/build-windows.yml/badge.svg)](https://github.com/felipeida08-bit/osu-mp-link-miner/actions/workflows/build-windows.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Aplicativo com interface grafica e linha de comando para encontrar partidas
multiplayer publicas do osu! das quais um jogador participou. O programa resolve
o nickname para o ID permanente da conta, percorre as partidas recentes e salva
os links encontrados em JSON, CSV ou TXT.

## Baixar e usar no Windows

1. Baixe o arquivo `osu-mp-link-miner.exe` na pagina de
   [Releases](https://github.com/felipeida08-bit/osu-mp-link-miner/releases/latest).
2. Crie uma aplicacao OAuth nas
   [configuracoes da sua conta osu!](https://osu.ppy.sh/home/account/edit#new-oauth-application).
   Informe um nome para a aplicacao. O callback pode ficar vazio, pois o programa
   usa Client Credentials.
3. Abra o executavel e preencha seu nickname, o **Client ID** e o
   **Client Secret** fornecidos pelo osu!.
4. Defina um limite de paginas (cada pagina lista ate 50 partidas) ou deixe
   `0` para continuar ate clicar em **Parar**. Clique em **Iniciar fila**.

O botao **Como obter credenciais?** da propria interface abre a pagina correta.
Cada pessoa deve usar as suas proprias credenciais. Nunca publique nem envie seu
Client Secret para outra pessoa.

O executavel e gerado automaticamente a partir do codigo deste repositorio.
O arquivo `.sha256` da mesma Release permite conferir a integridade do download:

```powershell
Get-FileHash .\osu-mp-link-miner.exe -Algorithm SHA256
```

## Recursos

- busca da partida mais recente para a mais antiga;
- ate 5 verificacoes concorrentes por padrao;
- intervalo global minimo de uma requisicao por segundo;
- renovacao automatica do token OAuth em buscas longas;
- parada por data, quantidade de paginas ou pelo botao **Parar**;
- verificacao direta por MP ID ou link completo;
- exportacao em JSON, CSV e TXT;
- duplo clique para abrir uma partida no navegador.

O campo **Verificar um MP diretamente** aceita tanto `121788519` quanto
`https://osu.ppy.sh/community/matches/121788519`.

### Credenciais locais

No Windows, marque **Lembrar credenciais neste computador** se quiser restaurar
os campos na proxima abertura. O Client ID fica na configuracao local e o Client
Secret e protegido pelo Windows DPAPI para o usuario atual. Desmarcar a opcao
remove as credenciais salvas ao fechar.

Em Linux e macOS, o armazenamento local fica desativado: informe as credenciais
a cada abertura ou use as variaveis de ambiente descritas abaixo. O segredo
nunca e incluido no repositorio nem nos arquivos de resultado.

## Executar pelo codigo-fonte

Requer Python 3.10 ou mais recente. O aplicativo usa somente a biblioteca padrao
do Python em tempo de execucao.

```powershell
git clone https://github.com/felipeida08-bit/osu-mp-link-miner.git
cd osu-mp-link-miner
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python gui.py
```

No Linux ou macOS, ative o ambiente com `source .venv/bin/activate`. Algumas
distribuicoes Linux exigem a instalacao separada do pacote `python3-tk`.

## Linha de comando

As credenciais podem ser fornecidas por variaveis de ambiente:

```powershell
$env:OSU_CLIENT_ID = "SEU_CLIENT_ID"
$env:OSU_CLIENT_SECRET = "SEU_CLIENT_SECRET"

# Examina ate 1.000 partidas recentes
python .\mp_miner.py "Nickname" --pages 20

# Para em uma data e salva somente os links
python .\mp_miner.py "Nickname" --pages 100 --since 2026-08-01 --format txt
```

Em bash, use `export OSU_CLIENT_ID="..."` e
`export OSU_CLIENT_SECRET="..."`. Tambem e possivel passar
`--client-id` e `--client-secret` diretamente, mas isso pode deixar o segredo
visivel no historico do terminal.

Use `python mp_miner.py --help` para ver todas as opcoes.

## Limitacoes

A API v2 nao oferece uma busca de partidas legadas por jogador. Por isso, o
programa percorre a listagem global e consulta cada partida, o que pode levar
tempo. Salas modernas do osu!lazer usam outro sistema (`/rooms`) e nao fazem
parte desta busca.

O projeto consulta apenas dados publicos disponibilizados pela API oficial.
Respeite os [termos da osu!api](https://osu.ppy.sh/docs/#terms-of-use) e evite
buscas continuas desnecessarias.

## Desenvolvimento

Executar os testes:

```powershell
python -m unittest discover -s tests -v
```

Gerar o executavel do Windows:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\build.ps1
```

O diretorio `dist/` e ignorado de proposito: binarios gerados nao ficam no
historico Git. Ao enviar uma tag `v*`, o GitHub Actions cria o executavel,
calcula seu SHA-256 e publica os dois arquivos em uma GitHub Release:

```powershell
git tag v1.0.0
git push origin v1.0.0
```

## Licenca

Distribuido sob a [licenca MIT](LICENSE).
