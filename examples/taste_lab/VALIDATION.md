# Initial validation — November 17, 2026

These observations describe one development profile, not a recommendation-quality
benchmark across users. The experiment has not demonstrated superiority to Spotify.

## Live, read-only import and retrieval

- Imported 579 liked-track records, 36 saved playlists and 14 saved albums.
- Read 13,994 membership records before within-source deduplication; no source failed.
- Initial retrieval with eight seed artists and five neighbors cached 912 unique
  tracks. One artist request failed; the partial result was reported explicitly.
- No playback, playlist or Spotify library mutations were requested.

## Artist-disjoint retrospective diagnostic

The deterministic split left 5,500 unique training tracks and 2,197 withheld
tracks after removing overlapping artists/collaborations. Fresh retrieval used
only the training partition, producing 571 eligible candidates and six reported
artist-request failures. Only three withheld tracks were retrieved.

At ten recommendations, metadata ranking recovered zero withheld positives;
the popularity baseline also recovered zero. The mean across 100 seeded random
draws was 0.01 hits. Retrieval recall was 0.0013655 (0.137%). There was no personal
audio coverage, so no audio-quality result was available.

**Interpretation:** the small artist-neighbor candidate pool has very low coverage
of this broad library. These results do not validate the ranker. They also cannot
establish that any unfamiliar recommendation is bad: those songs were unlabeled.
Broader independently sourced candidates, verified recording matches, personal
audio coverage and blinded listening judgments remain necessary.

## Real audio inference

The pinned `laion/clap-htsat-unfused` checkpoint ran on CPU using Transformers
4.57.6 and PyTorch 2.15.0 on Windows, with generated tones as the input. It produced
three normalized 512-dimensional section embeddings. Repeated inference had
cosine similarity 0.9999999999999999; changing the generated tone from 220 Hz to
880 Hz yielded cosine similarity 0.8418643.

This confirms decoding, resampling, checkpoint compatibility and reproducible
inference. It does not demonstrate musical understanding, preference prediction
or an appropriate universal cosine threshold. The initial checkpoint-loading
failure was fixed before this successful run.

## Automated checks

The full read-only suite passed: **578 tests passed, four mutation tests skipped**.
Strict type checking, linting and formatting checks also passed.

The focused tests cover transactional import recovery, nested-folder traversal,
feedback idempotency, retained discovery anchors, future-event isolation, cautious
playback attribution, cooldowns, artist diversity, embedding validation, separate
taste clusters, feedback propagation and model-version isolation. Synthetic tests
measure those contracts, not how much listeners enjoy the output.

Run the commands in the README to reproduce checks against your own profile.
Network results can differ as Spotify and the library change.

## Follow-up implementation checks

Automatic temporary audio sampling subsequently analyzed 14 real recordings in
the development profile. Ambiguous matches were skipped, not guessed. One
ten-track recommendation slate used audio for one result and included four artists
absent from the imported library. This demonstrates an end-to-end path; it is not
a listening-quality result or a controlled comparison of audio models.

Adding bounded discovered-on playlist samples increased the production pool to
1,224 tracks. A fresh artist-disjoint retrieval recovered 32 withheld positives
from 2,196 withheld tracks (1.46%) in a 782-track eligible pool. The metadata ranker
still recovered zero positives at ten. The deterministic random baseline averaged
0.37 hits and the popularity baseline recovered zero. Audio had no candidate
coverage in this isolated pool, so its ranking metric was unavailable. **Retrieval
improved; ranking superiority remains unproven.**

The benchmark is now saved separately from production candidates and can be rerun
with `evaluate --cached`, without network access or candidate-pool drift. Random
sampling uses sorted identities so task completion order cannot change its result.
Imported artist credits are protected from partial candidate metadata during
refresh. The focused example suite now contains 45 passing tests; strict typing,
lint and formatting checks pass. The last full read-only regression run passed
585 tests with four mutation tests skipped, before two further focused regression
tests were added for metadata preservation and baseline reproducibility.
