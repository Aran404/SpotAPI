# SpotAPI

**Ferramentas do Spotify para Python, com aplicativos prontos para usar.**

[English](README.md) · **Português (Brasil)** · [Español](README.es.md)

SpotAPI é uma biblioteca Python assíncrona e tipada para consultar dados públicos do catálogo do Spotify, trabalhar com playlists e controlar players existentes. **Consultas públicas não exigem criar um aplicativo de desenvolvedor nem fornecer uma chave de API.** A biblioteca usa interfaces não oficiais do web player, que podem mudar.

## Comece em segundos

Requer Python 3.11 ou superior.

\`\`\`bash
python -m pip install spotapi
python -m spotapi search "Daft Punk"
\`\`\`

A mesma instalação permite usar a API diretamente:

\`\`\`python
import asyncio
from spotapi import Public

async def main():
    results = await Public.search("Daft Punk", limit=5)
    for track in results.tracks:
        print(track.name, track.uri)

asyncio.run(main())
\`\`\`

## Aplicativos sem escrever código

- **Discover:** navegue por músicas e metadados no terminal. Instale com \`python -m pip install "spotapi[demo]"\` e execute \`python -m spotapi discover "Daft Punk"\`.
- **Connect:** controle um player Spotify existente pelo terminal. Instale com \`python -m pip install "spotapi[connect]"\` e execute \`python -m spotapi connect\`. É necessário ter uma sessão Spotify para controlar a reprodução. Se o extra ainda não estiver no PyPI, consulte a seção Connect do [README em inglês](README.md#connect-control-your-spotify-player).
- **Studio:** explore músicas, créditos e letras sincronizadas em um aplicativo desktop. Instale com \`python -m pip install "spotapi[studio]"\` e execute \`python -m spotapi studio\`.

O projeto não transmite, baixa nem descriptografa músicas completas. A disponibilidade dos controles depende da conta e do dispositivo.

## Crie suas próprias ferramentas

A API permite consultar playlists, analisar dados, exportar resultados e desenvolver integrações. O [exemplo de auditoria de playlists](examples/playlist_audit.py) exporta ocorrências para CSV sem carregar toda a playlist na memória.

Leia o [README principal](README.md), a [documentação](https://spotapi.readthedocs.io/) e os [exemplos](examples/README.md) para conhecer as funcionalidades e limitações atuais.

**Código aberto e independente do Spotify.** Use o projeto conforme as leis e condições de acesso aplicáveis. [Licença GPL-3.0](LICENSE) · [Contribuir](CONTRIBUTING.md) · [Apoiar o projeto](SPONSORSHIP.md).
