# SpotAPI: completeness, private contracts and readable design

Research update: November 12, 2026. This supersedes the feature priorities in the
previous growth plan. Adoption and reach guide priorities; clear code and
verified behaviour must support the first-run experience. Proposed interfaces
below are designs, not shipped methods.

## Release audit: November 13, 2026

This section records checks repeated against this working tree. Earlier live
observations below are historical evidence, not certification of today's build.

- Python 3.12 on Windows: 435 offline tests passed; 29 live cases deselected.
- Strict Pyright, Ruff and Black passed. This does not establish correctness
  of endpoints whose responses were mocked.
- Strict MkDocs documentation and wheel/source builds passed. Combined
  statement/branch coverage was 74.5%; catalogue and CLI paths remain around
  55%. Passing tests should not be described as exhaustive coverage.
- Fixed `SyncCatalogue.close()` when called inside an existing event loop:
  reject the call before changing ownership or constructing close coroutines.
  The regression checks that the client remains usable and closes once later.
- Keyboard tests verify Escape and Down leave Discover's search input and
  focus the results without a mouse.
- CI now includes Windows and macOS on Python 3.12 alongside Linux on
  Python 3.11–3.13, with separate coverage artifacts and bounded job duration.
  These hosted jobs have not run as part of this local audit.
- Ordinary HTTPS reached Spotify and PyPI. PyPI currently reports version
  2.0.0; that does not establish that this checkout's additions are published.
- Cold startup was traced to eager downloads of 168 web-player bundles. Bootstrap
  now loads the main and search-route bundles first; other queries share locked,
  on-demand discovery. Eight workers continue downloading without batch barriers.
  Live search then passed with two bundle requests in 21.3 seconds, versus an
  earlier 80.9-second run. A typed track lookup passed too. These observations
  used the environment's explicit proxy and are not latency guarantees.
- Authenticated authorization, profile and plan reads passed separately. The
  broader read-only run completed six public cases before its four-minute limit;
  it does not establish complete live coverage. No account writes were submitted.
- The artist-discovered-on live contract passed separately in 107.5 seconds.
  Its first call required discovering the remaining route chunks. Search's
  reduced bootstrap does not imply every operation has the same cold latency.
- Discover releases image caches even if feed shutdown fails. Injected query
  scopes no longer silently fall back to anonymous embeds. Authentication tests
  check independent RFC 6238 vectors and TOTP bundle/version selection.
- The quickstart connects CLI, terminal browsing, Studio source and a reusable
  Python client. JSON export is a complete runnable example. No new runtime
  dependency, public API layer or source file was added in this hardening pass.

This is a focused audit and regression pass, not a claim that every line of
SpotAPI or discord.py has been reviewed. There is no measured repository
visitor drop-off or causal evidence that changing the README produces stars.

### Scope and positioning

[Spotifast](https://github.com/crmne/spotifast) advertises a native desktop
player. Its README permits free-account browsing and search while requiring
Premium for playback. The linked
[Reddit post](https://www.reddit.com/r/BestGitHubRepos/comments/1xbjzzv/spotifast_spotify_native_and_fast_86k_stars/)
records 8,585 stars; the retrieved repository displays about 10.3k. Those
snapshots do not establish which promotion caused its growth, or demand for
a Python wrapper. Do not present SpotAPI's lack of audio streaming as a
free substitute for Premium playback.

The launch promise should remain concrete: search Spotify from a terminal
without creating a developer app, then reuse typed results in Python. Account
workflows, explicit resource ownership and playlist occurrence editing support
that promise. Studio demonstrates what users can build; it should not require
turning the library into a competing desktop player.

Do not add YouTube matching, audio downloading or another playback backend
to this release. Matching correctness, external dependencies and backend
breakages would need their own maintenance and verification. Retain useful
metadata and explicitly available media assets within the existing API.

### Launch gates and distribution experiments

1. Resolve live search and run public plus authenticated read contracts on the
   exact release wheel. Confirm the documented CLI commands in a clean install,
   outside the checkout. Finish strict docs and artifact checks. Hosted CI must
   pass on supported platforms before calling the release ready.
2. Ask five independent developers to install the wheel and complete search,
   link lookup and a small Python integration without coaching. Record failures,
   setup time and confusing terminology. Fix observed friction before outreach.
   Five testers are a discovery exercise, not statistical proof of conversion.
3. Make a short terminal recording that shows installation, a real search,
   keyboard browsing and the equivalent Python result. Lead the README and
   launch post with this workflow; keep account setup and advanced integrations
   in linked Read the Docs guides. Do not advertise unpublished commands.
4. Promote the existing `examples/export.py` and `examples/public_search.py`
   recipes for playlist metadata export and reusable catalogue search. The
   quickstart now links both, using the shared JSON exporter and one catalogue
   scope. Ask willing users to share projects in a showcase discussion instead
   of adding recipe-specific abstractions or more example files.
5. Publish a technical write-up about one verified design choice, such as
   duplicate playlist occurrences or explicit async ownership. Submit the
   useful recipe or write-up to relevant Python newsletters and community
   showcases, following their submission rules. This is a proposed experiment,
   not a claim that those channels will accept it. No messages were sent.
6. Launch HN only after the gates pass. Separately test a Python-community post
   and a Spotify-tooling post with audience-specific examples. Use one channel
   at a time so traffic changes are easier to interpret. Answer technical
   questions and fix reproducible failures rather than repeatedly posting links.
7. Record a baseline and weekly repository visitors, clones, stars, package
   downloads and reported first-run failures. Distinguish downloads from unique
   users and stars from adoption. GitHub traffic is aggregated; it cannot prove
   that an individual visitor ran the CLI. Compare outreach windows cautiously.

One thousand stars is a goal, not a forecast. Review the experiments after two
weeks of a stable release; change examples and distribution based on observed
interest instead of expanding the feature list to compensate for low reach.

## What the research establishes

SpotAPI is not yet a verified superset of competing Spotify libraries. It has
substantial catalogue, account, playlist and Connect functionality, but a method
name, an operation enum member and a successful live workflow are different
levels of evidence. The goal is a coherent library for Spotify applications,
with explicit support boundaries and reasons to adopt particular workflows.

This pass inspected the current SpotAPI source and declarations, current Spotify
Web API documentation, Spotipy, Tekore, SpotifyScraper, SpotifyWebApiPython,
librespot and spotDL. Additional async-client projects were discovered as leads.
Their advertised features are not automatically verified working endpoints.
The accompanying contracts.json records local method declarations and reconciles
an earlier web-player inventory against the CURRENT source rather than repeating
its obsolete spotapi/v2 paths or treating enum counts as coverage.

The browser showed an authenticated Spotify session during inspection. No .env
cookie was printed, copied into a report, or sent to another service. Authentication
appeared in the browser; this pass does not claim to have imported .env cookies.
Inspected pages: What’s New, Settings, a playlist, its action menu and its Mix
entry point. No playlist edits, downloads, settings changes, social invitations,
or playback commands were submitted. Existing playback continued independently.

I inspected relevant discord.py source sections: HTTP routes/rate limiting,
client lifecycle/events, user objects and wire TypedDicts, plus its quickstart.
This is NOT a full read of the entire repository. Direct source download failed
and several source pages were only partially retrievable. A full-repository
review remains outstanding; it would be misleading to certify it complete.

## Sources and what each contributes

| Source | Observed strength | Implication for SpotAPI |
|---|---|---|
| [Spotipy](https://spotipy.readthedocs.io/en/latest/) | Web API coverage and OAuth flows | Cookie support alone is not a substitute for official authorization in multi-user applications. |
| [Tekore](https://tekore.readthedocs.io/en/stable/) | Typed Web API usage, async support and authentication | Async and types are useful baseline requirements, not sufficient differentiation. |
| [SpotifyScraper](https://github.com/AliAkhtari78/SpotifyScraper) | Key-free metadata, media, transcripts, batching, sessions and MCP | Most corresponding implementations exist in this checkout; integration/live verification is still uneven. |
| [SpotifyWebApiPython](https://github.com/thlucas1/SpotifyWebApiPython) | Broad Web API method inventory, authorization and device-control integration | Compare complete workflows, including account and device setup. Its README can describe endpoints restricted for newer apps. |
| [librespot](https://github.com/librespot-org/librespot) | Native Spotify client, Connect receiver and audio playback | These are different responsibilities from controlling an existing player; never imply that SpotAPI renders audio. |
| [spotDL](https://github.com/spotDL/spotify-downloader) | Finds matching YouTube audio, adds metadata, exposes CLI workflows | Optional external-source downloading is feasible as an integration, with matching provenance and separate dependencies. |
| [HTTPX](https://www.python-httpx.org/) | Simple initial request, reusable clients, explicit async support and transport controls | Preserve familiar operations while providing a gradual path into advanced configuration. |
| [discord.py HTTP](https://github.com/Rapptz/discord.py/blob/master/discord/http.py) | Routes describe paths; transport owns request/rate-limit policy | Keep URL construction and protocol policy out of application-facing methods. |
| [discord.py client](https://github.com/Rapptz/discord.py/blob/master/discord/client.py) | Explicit lifecycle and named event dispatch | Document ownership, readiness and event/error behavior consistently. |
| [discord.py user](https://github.com/Rapptz/discord.py/blob/master/discord/user.py) | Domain objects expose useful behavior through shared state | Consider ergonomic resource helpers only where they reduce work without hiding I/O or ownership. |
| [discord.py wire types](https://github.com/Rapptz/discord.py/blob/master/discord/types/channel.py) | Protocol TypedDicts are distinct from user-facing objects | Keep wire contracts private; do not force consumers to learn native payload spellings. |

Other discovered clients worth extending the ledger with after source retrieval:
[spotify.py](https://github.com/mental32/spotify.py),
[aiospotipy](https://github.com/sizumita/aiospotipy), and
[pyfy](https://github.com/omarryhan/pyfy). No maintenance or complete-parity claim
is made about these projects merely because they were discoverable.

## Official API facts that changed the comparison

The [February migration guide](https://developer.spotify.com/documentation/web-api/tutorials/february-2026-migration-guide)
distinguishes Development Mode from Extended Quota Mode. It changes library and
playlist contracts, reduces some Development Mode capabilities and preserves
existing user counts above the new limit. OAuth scopes, markets and entitlement
remain separate concerns from a public anonymous read.

The [March update](https://developer.spotify.com/documentation/web-api/references/changes/march-2026)
retains track and album external_ids. The
[May update](https://developer.spotify.com/documentation/web-api/references/changes/may-2026)
adds account_id as a stable account-linking identifier. The
[July update](https://developer.spotify.com/documentation/web-api/references/changes/july-2026)
increases the app limit to 25 and shares Development Mode quota across a developer
account. The README’s one-app limit and blanket grandfathering statement were
therefore incorrect and have been corrected. Do not use old API restrictions as
an exaggerated reason to switch.

Spotify publishes an [OpenAPI schema](https://developer.spotify.com/reference/web-api/open-api-schema.yaml).
Its download was blocked by the research tool's YAML handling here, so there is
no freshly parsed exhaustive official-endpoint inventory in this pass. That
inventory and app-mode annotations remain a completion gate, not an implied pass.

## Capability ledger: aggregate useful jobs, preserve differences

Present means an implementation was inspected, not that all live states passed.
Partial means that important behaviors or contracts remain missing/unverified.

| Capability group | Current SpotAPI surface | Gap / action |
|---|---|---|
| Search and entity lookup | Public, Catalogue; normalized IDs/URIs/URLs | Present; verify sparse and regional cases. |
| Official market selection and track relinking | Display-language configuration and web-player regional results | Partial: language is not market. Preserve relink identity and account-market semantics in any official backend. |
| Full audio features and detailed analysis | Optional playlist BPM/key fields | Not equivalent. Verify access per app/source; do not fabricate removed data or call local estimates Spotify measurements. |
| Browse categories, genre seeds and available markets | Genre search exists; native browse leads | Search categories are not browse/category endpoints. Finish their distinct contracts where accessible. |
| Albums, shows, episodes, books and chapters | Typed catalogue getters and page streams | Chapter detail still has a raw escape-hatch path; finish typed per-chapter identity/availability before claiming uniform coverage. |
| Artist top tracks, releases and related artists | Catalogue methods | Present; do not confuse overview lists with complete discography. |
| Artist discovery placements | get_artist_discovered_on added in this pass | Prior authenticated shape evidence; unavailable slots retained; fresh managed-client live gate pending. |
| Artwork, palette, Canvas and previews | get_colors/get_canvas/get_embed; Media | Present; partial availability and explicit sparse fallback. |
| Credits, concerts, album recommendations, chart shortcuts | Catalogue discovery helpers | Present; charts are selected playlists, not historical rank analytics. |
| Public profiles and connections | Catalogue.get_profile; Profiles | Capped previews and first pages differ from exhaustive results. |
| Saved tracks and generic saved content | LikedTracks; Library get/pages/items/add/remove/contains | Generic save operations already exist; add domain-specific pagination only when native filters are verified. |
| Top content and recent listening | ListeningStats; ListeningHistory | Affinity is not play count; recent contexts are not full listening history. |
| Playlist and folder management | Playlist; PlaylistHandler; Library pin/unpin | Present; strengthen revision/conflict handling and exact occurrence semantics. |
| Atomic replacement and caller-controlled playlist conflicts | Existing add/remove/move operations and native revisions | Explicit replacement/conflict guarantees need separate review; a remove-then-add sequence is not atomic replacement. |
| Playback and queue control | Player and PlayerStatus | Present; live events and exact queue occurrence edits are useful advantages over simple Web API clients. |
| Control-device registration | Player registration helpers | Present; is not audio decoding or LAN discovery of every speaker. |
| Lyrics and podcast captions | Account-composed helpers | Present; current entitled caption integration needs live checks. |
| Book/podcast resume position and consumption progress | Playback snapshots; no uniform verified progress API found | Recover progress reads and update semantics separately from player seek or metadata. |
| Browser login and saved credentials | browser_login; SavedSession | Present; platform/keyring/backend verification remains. |
| Official OAuth and application credentials | No complete supported Web API backend found | Real gap: PKCE, refresh, scope errors and app-mode-specific capabilities. Complement private contracts rather than replacing them. |
| Independent partial batch outcomes | fetch_many and Catalogue.fetch_many | Present; avoid a new plural alias for every resource. |
| Sync scripts | SyncCatalogue | Present; one shared async implementation. Notebook/event-loop limitations stay explicit. |
| Serialization, optional caching and MCP | Existing helpers | Present; metadata export does not make secrets safe automatically. |
| Browse/home/release feed | Native operation names in inventory; no complete domain API | High priority: finish read contracts, heterogeneous items and cursors. |
| Artist appears-on and richer discovery sections | Native operation leads | Useful next addition after request/response and paging evidence. |
| LAN discovery and speaker-specific activation | No complete equivalent found | Research SpotifyWebApiPython/Connect integrations; keep platform dependencies optional. |
| External-source audio download | Not implemented; previews only | Optional integration design below; do not label matched audio as a Spotify recording. |

## Private Spotify findings from this signed-in inspection

This table intentionally separates visible controls from recovered API behavior.
A feature's absence from the reviewed references does not prove no other wrapper
has ever implemented it. Premium is account entitlement, not universal API access.

| Candidate | Evidence now | Why useful / next concrete contract work |
|---|---|---|
| Taste-profile inclusion/exclusion | Playlist menu visibly offers exclusion | Useful for sleep/workout playlists. Recover state read + set operation, authentication and rollback; test on a temporary playlist. |
| Collaborator invitations | Playlist shows an invite action | Collaboration tools need link/expiry/permission semantics; do not generate or share invitations just to explore. |
| What’s New and following feeds | Signed-in feed exists; current account returned empty, with Music/Podcast feed links | A release notifier is useful; recover the actual cursor and union types. An empty feed is not a parsed API fixture. |
| Listening activity and taste comparison | Navigation and settings explain it; related bundle loaded | Distinct from affinity rankings. Determine authorized visible-user scope and read subscription lifecycle; avoid conflating presence with full listening history. |
| Playlist mixing/transitions | Mix opens a Windows-app-only prompt | Research desktop contracts separately. BPM/key fields alone do not implement Spotify’s transition editor. |
| Smart Shuffle | Signed-in player/playlist controls expose it | Basic shuffle already exists. Recover mode state and recommendation provenance before a new enum or setter. |
| Music-video associations | Now-playing UI lists related videos and a switch action | Existing Player switching is partial; recover associated resources, state transitions and devices supporting video. |
| Media preferences | Settings exposes separate music-video, Canvas and other-video controls | Determine which preferences are device-local versus account-synced before advertising remote settings. No preferences were changed. |
| Prompted playlist creation | Current promptedPlaylists bundle observed | An asset name is only an eligibility/research lead. Confirm this account can reach the UI and inspect mutation contracts before implementation. |
| Comments/replies/reactions | Current user-comments bundle; prior inventory includes operation names | Start with reads and entitlement. Do not post comments/reactions during research. |
| Listening statistics beyond affinity | A current listening-stats-modal bundle was observed | Recover actual units, time windows and response fields; do not present top-item rankings as measured minutes or play counts. |
| Explore playlist | Playlist displays Explore | Recover recommendation/feed identity and pagination; it may differ from existing playlist extender recommendations. |

Current observed asset examples (URLs contain no account credentials):
- https://open.spotifycdn.com/cdn/build/web-player/web-player.e762c0de.js
- https://open.spotifycdn.com/cdn/build/web-player/home-v2.bd615de5.js
- https://open.spotifycdn.com/cdn/build/web-player/dwp-promptedPlaylists.cd34b245.js
- https://open.spotifycdn.com/cdn/build/web-player/dwp-user-comments.8ee7098d.js
- https://open.spotifycdn.com/cdn/build/web-player/listening-stats-modal.cf9a8dcf.js

Bundle filenames changed from the November 10 inventory. This is why persisted
hashes, experiment-specific variables and source locations cannot be assumed
current. Script asset bodies and network traces were not available through the
browser's supported asset-export API, and direct CDN/source retrieval failed.
The pass therefore records fresh UI/asset observations and historical contract
evidence separately; it does not claim these new contracts were fully recovered.

## Reverse-engineering workflow and completion criteria

For each useful user job:

1. Observe its entry point and visible availability on an authorized account.
2. Identify the deployed source/call site or a sanitized request trace: service,
   method, operation/hash, variables, required headers and response union.
3. Record read/write semantics, whether navigation acknowledges or mutates state,
   cursor/revision handling, entitlement and device/market constraints.
4. Implement through the shared session and transport. No endpoint-specific token
   refresh code; no replay of ambiguous mutations; no secret-bearing fixtures.
5. Test successful, unavailable, malformed, canceled and multi-page behavior.
6. Run a read-only live sample. For state changes use isolated test resources,
   record prior state and verify restoration. Social actions require a suitable
   explicit test recipient rather than another real account chosen implicitly.
7. Publish the method, example and evidence status together. An unsupported native
   operation remains a research entry, not an automatically generated wrapper.

The ledger should track source checksum/build, request shape, response shape,
authentication, entitlement, pagination, replay policy, method, fixture and last
live result independently. Full private-API recovery is not a finite, provable
claim across all Spotify deployments. Listener Premium does not grant creator,
ads, publishing, household-admin or every regional experiment role. Investigate
those surfaces independently if they solve a real user problem.

## Readability findings and changes

Actual current concentrations before these additions: Catalogue 1,472 lines,
Public 734, AsyncClient 637, AuthSession 929, Player 685 and PlayerStatus 760.
These counts identify review hotspots, not automatic reasons to split files.

| Finding | Smallest useful response |
|---|---|
| Radio and public-profile URLs still embedded inside Catalogue | Move construction to existing _protocol/routes.py; preserve the emitted radio URL including literal URI colons. No public signature changes. |
| Several layers named Queries, QueryClient, SharedQueryClient and AsyncClient | Document one call path per transport; prefer Catalogue for normal reads. Consolidate only after proving which layer can disappear without losing lifecycle/error behavior. |
| Page, item and one-shot iteration require learning separate semantics | Keep the established API, add consistent examples and cancellation checks; no further synonyms. |
| _parsing.mapping can turn malformed nested data into an empty mapping | Enforce required envelopes and discriminator types at feature boundaries. Discovery parsing added here rejects unknown/error shapes rather than pretending success. |
| Public/Catalogue/SyncCatalogue repeat related signatures | Keep explicit typed wrappers. Avoid __getattr__-generated methods that hide signatures and make docs/type checking worse. |
| Search and catalogue parsing share one large module | Split only coherent internal protocol parsing when a real next feature warrants it; do not create one file per endpoint. |
| New native operations tempt a giant generic proxy API | Expose domain jobs with Python names and typed outcomes. Wire names stay private. |
| Public models must remain safe to inspect | Retain ordinary data models with no implicit requests. Resource controllers such as Playlist can own explicit awaited operations. |
| Synchronous methods must not compete with an application's loop | Preserve one Runner per SyncCatalogue scope and clear failures in async contexts; do not add another network stack. |

The concrete lesson from discord.py is separation of responsibilities, deliberate
domain vocabulary and explicit async behavior. Its Route itself concatenates a
base and path internally: the problem is scattered construction, not that string
concatenation is intrinsically unprofessional. Discord’s server-specific rate
limit buckets and gateway state cannot simply be copied to Spotify.

Design rules for subsequent work: one clear owner of network resources; one
place for authentication and retry decisions; private typed wire contracts where
stable; domain models in models/; optional integrations grouped below a private
or integrations subpackage; no dynamic public-method generation; no second set
of synchronous algorithms; cancellation remains cancellation; error messages
explain the failed job. Prefer ordinary functions over a framework of registries.

## Optional non-DRM download integration

spotDL demonstrates a Spotify-metadata-to-YouTube-audio workflow. Its setup also
includes FFmpeg and may need additional YouTube runtime support. Those costs must
not enter the base wrapper dependency graph.

Recommended design: an optional integration under integrations/ that accepts a
resolved track or playlist stream and an explicit source/backend. Separate
resolve/match from download so the user can inspect candidate title, artist,
duration, source URL and confidence first. Preserve the chosen source and match
reason in the result. Distinguish studio/live/remix/cover versions and reject an
ambiguous match by default. Download only when requested, with explicit file paths,
no silent overwrite, bounded concurrency, cancellation cleanup and typed per-item
outcomes. Keep published Spotify previews on the existing Media path.

A future CLI could say `spotapi download audio ... --source youtube`; this is a
proposal, not an installed command. Do not use a generic download_track method
that suggests the file came from Spotify. Never forward Spotify cookies to the
external provider. No DRM/key extraction, no silent installation of binaries,
and no assumption that a publicly viewable upload grants download permission.

Before shipping: pin a supported backend interface, test matching quality against
a curated version-sensitive set, verify process cancellation on Windows/Linux,
check exit/error parsing and test packaging with the optional dependencies absent.
This pass did not implement or test external-source audio downloading.

## Adoption: evidence and specific experiments after the library gates

There is no private GitHub traffic, scroll-depth or conversion dataset here.
Consequently there is no evidence that visitors currently leave because of a
particular README section. I made factual comparison corrections, not an
engagement rewrite pretending such evidence exists.

Observed practices, not causal explanations of star growth:

- [Rich](https://github.com/Textualize/rich) offers an immediately runnable terminal
  demonstration and visual examples. Adaptation: put the exact successful CLI
  command and matching result in a short recording, then reveal the Python.
- [HTTPX](https://www.python-httpx.org/) starts with a familiar tiny request and
  exposes optional CLI and advanced client configuration progressively.
  Adaptation: keep a one-operation example, then reusable Catalogue, then account
  and player scopes. A user should not need transport vocabulary to start.
- [discord.py quickstart](https://discordpy.readthedocs.io/en/stable/quickstart.html)
  shows a small working event-driven application. Adaptation: an existing-player
  event example that users can modify into an overlay or status display.
- [FastAPI help](https://fastapi.tiangolo.com/help-fastapi/) directs durable
  questions into searchable GitHub discussions, offers release subscriptions and
  asks for a star explicitly. Adaptation: keep searchable answers, a release-only
  follow path and a single contextual star request; avoid CLI nags.
- [librespot](https://github.com/librespot-org/librespot) lists downstream projects.
  Adaptation: show real SpotAPI integrations with their maintainers’ consent,
  linking to working source and the feature each one uses.

Concrete distribution assets, beyond another HN/Reddit post:

| Asset | Intended user | Deliverable / success signal |
|---|---|---|
| Task-specific migration guide | Existing Spotipy/Tekore user missing one private feature | Side-by-side code, auth differences and known failures; a tester ports that one task successfully. |
| Playlist curator reference | Person building a playlist tool | Read/plan exact occurrence changes before applying; demonstrate duplicate preservation and conflict errors. |
| Release digest example | Music app/bot developer | Cursor-based release reads plus locally persisted state; notification transport supplied by their app. |
| Player overlay example | Streamer/dashboard developer | Typed events, stale/reconnected state and a minimal display; no clone of the entire Spotify UI. |
| Reproducible integration template | Developer choosing a new dependency | One maintained app template with working install/tests; user can change one small feature without reading protocol code. |
| Searchable issue-to-guide loop | Users already blocked by a task | Solve a reproducible issue, write the durable answer, add a regression fixture; link it where relevant without unsolicited mass outreach. |
| Versioned release notes | Existing users and cautious adopters | Show supported workflows and evidence changes, not inflated endpoint counts. |

Proposed first-use study: five developers unfamiliar with SpotAPI, one public
read and one account feature each. Record setup time, errors and whether they
can explain the ownership model. After verified releases, log weekly stars,
visitors, clones, docs referrals, first-use success and repeat integrations.
Neither a dopamine hypothesis nor a large competitor star count demonstrates
that a particular demo converts visitors. Test the path rather than treating
neuroscience language as product evidence.

## Execution order

1. Complete the current foundation: installed-wheel checks, optional-dependency
   isolation, reliable upstream contract tests, docs build and explicit API map.
2. Finish the best-supported private reads: artist placements (implemented here),
   following/release feeds, richer artist sections and video associations.
3. Recover taste-profile state and collaborator contracts. Implement mutations
   only after independent confirmation/rollback fixtures on test resources.
4. Investigate Premium differentiators: listening insights/activity, Smart Shuffle,
   desktop mixing and prompted playlists; document experiment/device limits.
5. Add official OAuth as an explicit supported integration mode and close the
   remaining official workflow gaps. Never silently swap a cookie session for an
   official token or assume both sources have identical fields and markets.
6. Add the optional external-source download adapter after matching/cancellation
   evaluation. Keep its release status and dependencies separate from metadata.
7. Publish task demonstrations and migration material only when they work from
   the actual released artifact. Then evaluate the 1,000-star goal weekly.

No star deadline overrides readable code, compatibility or evidence. A genuinely
useful aggregate can be built incrementally; claiming “every Spotify feature,
fully reverse engineered” now would misrepresent both the code and this research.

## Validation and remaining blockers

The earlier pass recorded 32 focused checks plus strict Pyright/Ruff/Black.
This pass adds a discriminator-aware artist-playlist parser, request identity
checks, async/public/sync facades, an opt-in live check and route regressions.
Observed new results: 37 focused route/model/parser checks passed; strict Pyright
reported zero errors, warnings or information diagnostics; Ruff and whitespace
checks passed. Changed Python files were formatted through Black's synchronous
API. The request-normalization test and opt-in live test were added but are not
included in that passing count.

Full async execution previously hung creating Windows’ loop socket pair; current
new endpoint live checks are not certified. Direct source/CDN download and package
installation are network-blocked. The browser session was usable for UI research
but did not expose authenticated network capture or script-body export. No HAR,
cookie, token, private playlist identity or personal response body is in the
committed ledger. Full discord.py review, exhaustive official-schema parsing,
new private request recovery and complete endpoint parity remain unfinished.
