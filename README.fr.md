<p align="center">
  <img src="assets/spotapi-icon.svg" width="112" alt="Logo SpotAPI">
</p>

<h1 align="center">SpotAPI</h1>

<p align="center">
  <strong>Créez des applications Spotify en Python avec une API typée et asynchrone.</strong>
</p>

<p align="center">
  Utilisez SpotAPI pour le catalogue public, les playlists et les lecteurs connectés de Spotify.<br>
  <strong>Aucune application développeur ni clé API requise pour les données publiques.</strong>
</p>

<p align="center">
  <a href="#bien-démarrer">Bien démarrer</a> ·
  <a href="#explorer-dans-le-terminal">Explorer</a> ·
  <a href="#développer-avec-python">API Python</a> ·
  <a href="https://the-open-odyssey.pages.dev/docs/spotapi/">Documentation</a> ·
  <a href="SPONSORSHIP.md">Parrainer</a>
</p>

<p align="center">
  <a href="https://discord.gg/vcFvvTuQzn"><img src="https://img.shields.io/badge/Discord-Join_The_Open_Odyssey-5865F2?style=for-the-badge&amp;logo=discord&amp;logoColor=white" alt="Rejoignez la communauté The Open Odyssey sur Discord"></a>
</p>

<p align="center">
  <strong>Langue :</strong> <a href="README.md">English</a> · <a href="README.pt-BR.md">Português (Brasil)</a> · <a href="README.es.md">Español</a> · Français · <a href="README.ja.md">日本語</a>
</p>

## Bien démarrer

Python 3.11 ou une version ultérieure est nécessaire. Commencez par une vraie recherche, sans connexion Spotify, identifiant client ni configuration.

```bash
python -m pip install spotapi
python -m spotapi search "Daft Punk"
```

Utilisez la même API en Python :

```python
import asyncio
from spotapi import Public

async def main():
    results = await Public.search("Daft Punk", limit=5)
    for track in results.tracks:
        print(track.name, track.uri)

asyncio.run(main())
```

[Autres exemples Python](#développer-avec-python) · [Audit de playlists et export CSV](examples/playlist_audit.py) · [Guide Python sans clé API](docs/no-api-key.md)

La première requête peut être plus lente pendant la découverte et la mise en cache des requêtes du lecteur Web.

Essayez l'explorateur interactif dans le terminal :

```bash
python -m pip install "spotapi[demo]"
python -m spotapi discover "Daft Punk"
```

Parcourez les résultats de recherche, les pochettes et les liens Spotify sans vous connecter. [Exemple Discover](https://github.com/Aran404/SpotAPI/blob/main/examples/discover.py) · [Dépannage](https://the-open-odyssey.pages.dev/docs/spotapi/troubleshooting/)

## Explorer dans le terminal

L'interface en ligne de commande ne se limite pas à la recherche. Examinez un artiste, récupérez les crédits d'un morceau ou listez le contenu d'une playlist publique :

```bash
python -m spotapi search "Daft Punk" --type artist --json
python -m spotapi get SPOTIFY_URL
python -m spotapi playlist items PLAYLIST_ID --limit 10
```

Ces commandes fonctionnent sans clé API développeur. Les opérations liées à votre compte — titres aimés, playlists privées et pilotage de votre lecteur Spotify existant — nécessitent votre propre session Spotify. Consultez le [guide du compte](https://the-open-odyssey.pages.dev/docs/spotapi/account/) et le [guide du lecteur](https://the-open-odyssey.pages.dev/docs/spotapi/player/).

### Connect : pilotez votre lecteur Spotify

Connect rassemble la recherche, la sélection d'appareil, la file d'attente, la lecture et un journal d'activité en direct dans une interface de terminal pensée pour le clavier. Il commande un lecteur Spotify existant sur lequel vous êtes connecté ; il ne **diffuse, télécharge ni déchiffre** les morceaux.

![SpotAPI Connect pilotant un véritable lecteur Spotify depuis le terminal](assets/cli-connect-demo.gif)

<p align="center"><sub>Connect · Recherchez, naviguez et pilotez un lecteur Spotify existant depuis votre terminal. Spotify lit l'audio ; SpotAPI envoie les commandes.</sub></p>

Lancez Connect :

```bash
python -m pip install "spotapi[connect,browser]"
python -m playwright install chromium
python -m spotapi connect
```

Ces commandes permettent une première connexion via le navigateur. Vous utilisez déjà `SPOTIFY_COOKIE` ou un profil Connect enregistré ? Installez uniquement `spotapi[connect]` et évitez le téléchargement du navigateur.

Utilisez `search Daft Punk`, `queue 1`, `pause`, `next` ou `seek 1:30`. `Ctrl+P` ouvre la palette de commandes. Consultez le [guide Connect](docs/connect.md) pour la sélection des appareils et la configuration.

## Découvrez ses autres possibilités

SpotAPI fait également fonctionner **Studio**, un explorateur musical de bureau construit avec la même bibliothèque. Ouvrez des titres, consultez les crédits, suivez des artistes et des albums, et affichez des paroles synchronisées. Avec un lecteur Spotify connecté, cliquer sur une ligne de paroles peut déplacer la lecture à cet instant.

![Aperçu de l'application de bureau SpotAPI Studio](examples/studio/preview.png)

[Voir la démonstration des paroles synchronisées (GIF, environ 11 Mo)](assets/lyrics-sync-demo.gif) · Studio lui-même ne diffuse pas de morceaux Spotify complets.

```bash
python -m pip install "spotapi[studio]"
python -m spotapi studio
```

Studio utilise une WebView native. La [configuration de Studio](https://the-open-odyssey.pages.dev/docs/spotapi/studio/) décrit les prérequis de chaque plateforme et la connexion à Spotify. La disponibilité des paroles dépend de leur source et des droits du compte ; se déplacer dans un morceau nécessite un lecteur authentifié et contrôlable.

## Soutenir SpotAPI

Les sponsors contribuent à maintenir SpotAPI gratuit et financent la maintenance, les tests et la documentation. [Devenir sponsor](SPONSORSHIP.md).

<details open>
<summary><strong>Sponsors</strong></summary>

<!-- Each sponsor gets a separate table. Add new cards before the closing details tag. -->

<table>
  <tr>
    <td width="100%">
      <p align="center"><a href="https://www.rapidproxy.io/?code=Z89BQULDV"><img src="assets/sponsors/rapidproxy.webp" width="220" alt="RapidProxy"></a></p>
      <p>Proxys résidentiels fiables pour l'automatisation en Python et la collecte de données Web. Plus de 90 millions d'adresses IP, ciblage mondial, sessions rotatives et persistantes et prise en charge de HTTP(S)/SOCKS5.</p>
      <sub>Sponsor rémunéré · Lien affilié. SpotAPI peut percevoir une commission sur les achats.</sub>
    </td>
  </tr>
</table>

</details>

## Développer avec Python

Réutilisez une session de catalogue pour les opérations liées :

```python
import asyncio
from spotapi import Catalogue


async def main() -> None:
    async with Catalogue() as spotify:
        results = await spotify.search("Daft Punk")
        if results.artists:
            artist = await spotify.get_artist(results.artists[0].uri)
            print(artist.name)


asyncio.run(main())
```

**Vous travaillez avec de grandes playlists ?** [Auditez jusqu'à 10 000 occurrences d'une playlist](examples/playlist_audit.py), repérez les titres en double et les entrées indisponibles, puis exportez un fichier CSV. L'exemple parcourt les résultats page par page au lieu de charger toute la playlist en mémoire. Exécutez-le depuis une copie locale du dépôt.

### Pour aller plus loin

| Votre projet | Par où commencer |
|---|---|
| Outils de recherche musicale ou de métadonnées publiques | [Catalogue public](https://the-open-odyssey.pages.dev/docs/spotapi/catalogue/) |
| Organisateur de playlists gérant correctement les doublons | [API Playlists](https://the-open-odyssey.pages.dev/docs/spotapi/account/) |
| Affichage du morceau en cours ou télécommande en direct | [Exemple de lecteur](https://github.com/Aran404/SpotAPI/blob/main/examples/player.py) |
| Tableau de bord musical personnel | [Compte et statistiques](https://the-open-odyssey.pages.dev/docs/spotapi/account/) |
| Sélection DJ basée sur le tempo et les tonalités harmoniques | [Sélection de playlist](https://github.com/Aran404/SpotAPI/blob/main/examples/playlist_crate.py) |
| Moteur expérimental local de recommandations musicales | [Taste Lab](https://github.com/Aran404/SpotAPI/blob/main/examples/taste_lab/README.md) |

## Pourquoi SpotAPI ?

- **Démarrez sans identifiants.** La recherche et les métadonnées du catalogue public ne nécessitent pas d'application développeur Spotify.
- **Résultats typés et asynchrones.** Utilisez des modèles Python plutôt que de deviner les clés de dictionnaires.
- **Entrées-sorties explicites.** Lire un modèle ne déclenche pas de requête HTTP supplémentaire à votre insu.
- **Au-delà des métadonnées en lecture seule.** Avec votre session authentifiée, gérez les titres enregistrés, modifiez les occurrences dans les playlists et contrôlez les lecteurs existants.
- **Conçu pour l'exploration.** Utilisez la CLI, Discover et Studio pour découvrir les fonctionnalités avant de les intégrer à votre code.

SpotAPI utilise des points de terminaison non officiels du lecteur Web de Spotify ; son comportement peut donc changer si Spotify les modifie. Il ne remplace **pas** l'API Web officielle pour tous les usages, et l'accès aux données publiques diffère de l'accès authentifié aux fonctions de lecture. [Comparer les API](https://the-open-odyssey.pages.dev/docs/spotapi/from-spotipy/) · [Limites des vérifications](https://the-open-odyssey.pages.dev/docs/spotapi/release-checks/#boundaries)

## Documentation et migration

[Démarrage rapide](https://the-open-odyssey.pages.dev/docs/spotapi/quickstart/) · [Référence de l'API](https://the-open-odyssey.pages.dev/docs/spotapi/reference/) · [Migration depuis Spotipy](https://the-open-odyssey.pages.dev/docs/spotapi/from-spotipy/) · [CLI et découverte](https://the-open-odyssey.pages.dev/docs/spotapi/discovery/) · [Dépannage](https://the-open-odyssey.pages.dev/docs/spotapi/troubleshooting/)

**Vous venez de la v1 ?** SpotAPI 2 privilégie l'asynchrone et comporte des changements incompatibles. Les applications v1 existantes peuvent fixer la version `spotapi==1.2.8` pendant la migration, ou utiliser `SyncCatalogue` pour de nouveaux scripts synchrones. Lisez le [guide de migration](MIGRATION.md).

## Contribuer

Les signalements de bogues, les problèmes reproductibles et les contributions réfléchies sont les bienvenus. [Contribuer](CONTRIBUTING.md) · [Tests](tests/README.md) · [Mentions légales](LEGAL_NOTICE.md) · [GPL-3.0](LICENSE)

Si SpotAPI vous aide à développer quelque chose, **[attribuez une étoile au dépôt](https://github.com/Aran404/SpotAPI)** pour aider d'autres développeurs à le découvrir.
