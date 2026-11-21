# SpotAPI

**Herramientas de Spotify para Python, con aplicaciones listas para usar.**

[English](README.md) · [Português (Brasil)](README.pt-BR.md) · **Español**

SpotAPI es una biblioteca de Python asíncrona y tipada para consultar datos públicos del catálogo de Spotify, trabajar con listas de reproducción y controlar reproductores existentes. **Las consultas públicas no requieren crear una aplicación de desarrollador ni obtener una clave API.** Usa interfaces no oficiales del reproductor web, que pueden cambiar.

## Empieza en segundos

Requiere Python 3.11 o posterior.

\`\`\`bash
python -m pip install spotapi
python -m spotapi search "Daft Punk"
\`\`\`

La misma instalación permite utilizar la API directamente:

\`\`\`python
import asyncio
from spotapi import Public

async def main():
    results = await Public.search("Daft Punk", limit=5)
    for track in results.tracks:
        print(track.name, track.uri)

asyncio.run(main())
\`\`\`

## Aplicaciones sin escribir código

- **Discover:** explora música y metadatos desde la terminal. Instala con \`python -m pip install "spotapi[demo]"\` y ejecuta \`python -m spotapi discover "Daft Punk"\`.
- **Connect:** controla un reproductor de Spotify existente desde la terminal. Instala con \`python -m pip install "spotapi[connect]"\` y ejecuta \`python -m spotapi connect\`. Se necesita una sesión de Spotify para controlar la reproducción. Si el extra aún no está en PyPI, consulta la sección Connect del [README en inglés](README.md#connect-control-your-spotify-player).
- **Studio:** explora música, créditos y letras sincronizadas en una aplicación de escritorio. Instala con \`python -m pip install "spotapi[studio]"\` y ejecuta \`python -m spotapi studio\`.

SpotAPI no transmite, descarga ni descifra canciones completas. La disponibilidad de los controles depende de la cuenta y del dispositivo.

## Crea tus propias herramientas

La API permite consultar listas de reproducción, analizar datos, exportar resultados y desarrollar integraciones. El [ejemplo de auditoría de playlists](examples/playlist_audit.py) exporta las entradas a CSV sin cargar toda la lista en memoria.

Consulta el [README principal](README.md), la [documentación](https://spotapi.readthedocs.io/) y los [ejemplos](examples/README.md) para conocer las funciones y limitaciones actuales.

**Código abierto e independiente de Spotify.** Utiliza el proyecto de acuerdo con las leyes y las condiciones de acceso aplicables. [Licencia GPL-3.0](LICENSE) · [Contribuir](CONTRIBUTING.md) · [Patrocinar el proyecto](SPONSORSHIP.md).
