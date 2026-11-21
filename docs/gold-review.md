# Gold pilot v0.2.1 - human review table (10/10 records)

File `data/gold/gold_pilot.jsonl`, sha256 `082dfe0adbd4af84...`. Policy: `docs/annotation-guidelines.md` (provisionally approved). **v0.2.1: all 10 records owner-verified (`human_verified=true`) on 2026-11-19.** Source: https://www.cameramoda.it/en/milano-moda-donna/calendar/ (captured 2026-11-19). No independent corroboration exists.
Check each row against the live page: *Source row* is the verbatim calendar row under the stated day heading. *Extracted* = what the gold expects a correct extractor to output. `2nd` = machine second pass (different parsing route + live drift check) - guards extraction errors only.

| # | id | day | source row (verbatim) | extracted: name / brand / type / date_time / venue | venue status | kind | 2nd | ambiguities | OK / fix / drop |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 13639 | 2026-09-22 | `F \| 14:00 live \| PRADA \| Via Lorenzini, 14` | PRADA / PRADA / fashion show / 2026-09-22T14:00 / Via Lorenzini, 14 | address | listed_show_entry | pass | tz?, live | |
| 2 | 13700 | 2026-09-22 | `F \| 20:00 \| VOGUE WORLD: MILANO \|` | VOGUE WORLD: MILANO / null / fashion show / 2026-09-22T20:00 / null | unpublished | unclassified_entry | pass | tz?, not-brand, venue_unpublished_null | |
| 3 | 13645 | 2026-09-23 | `F \| 10:30 live \| JIL SANDER * \| Location in the invitation` | JIL SANDER * / JIL SANDER * / fashion show / 2026-09-23T10:30 / null | invitation_only | listed_show_entry | pass | tz?, *, venue_invitation_only_null, map_coordinates_placeholder_ignored, live | |
| 4 | 13646 | 2026-09-23 | `F \| 11:30 live \| DANIELA GREGIS \| Piazza Sant'Ambrogio, 23A` | DANIELA GREGIS / DANIELA GREGIS / fashion show / 2026-09-23T11:30 / Piazza Sant'Ambrogio, 23A | address | listed_show_entry | pass | tz?, live | |
| 5 | 13685 | 2026-09-23 | `F \| 18:00 live \| MM6 MAISON MARGIELA * \| Location In The Invitation` | MM6 MAISON MARGIELA * / MM6 MAISON MARGIELA * / fashion show / 2026-09-23T18:00 / null | invitation_only | listed_show_entry | pass | tz?, *, venue_invitation_only_null, map_coordinates_placeholder_ignored, live | |
| 6 | 13691 | 2026-09-24 | `F \| 10:30 live \| GENNY \| Via Rubattino, 56` | GENNY / GENNY / fashion show / 2026-09-24T10:30 / Via Rubattino, 56 | address | listed_show_entry | pass | tz?, live | |
| 7 | 13669 | 2026-09-25 | `F \| 11:30 live \| SPORTMAX \| Corso Magenta, 24` | SPORTMAX / SPORTMAX / fashion show / 2026-09-25T11:30 / Corso Magenta, 24 | address | listed_show_entry | pass | tz?, live | |
| 8 | 13659 | 2026-09-26 | `F \| 10:30 live \| ERMANNO SCERVINO \| Piazza Lina Bo Bardi, 1` | ERMANNO SCERVINO / ERMANNO SCERVINO / fashion show / 2026-09-26T10:30 / Piazza Lina Bo Bardi, 1 | address | listed_show_entry | pass | tz?, live | |
| 9 | 13652 | 2026-09-27 | `F \| 11:00 live \| GIORGIO ARMANI \| Via Bergognone, 59` | GIORGIO ARMANI / GIORGIO ARMANI / fashion show / 2026-09-27T11:00 / Via Bergognone, 59 | address | listed_show_entry | pass | tz?, live | |
| 10 | 13648 | 2026-09-28 | `F \| 10:00 \| NADYA DZYAK \| DIGITAL` | NADYA DZYAK / NADYA DZYAK / fashion show / 2026-09-28T10:00 / null | digital | listed_show_entry | pass | tz?, venue_digital_null | |

Legend: `tz?` no timezone published (kept local) · `live` the word 'live' in the time cell is ignored · `*` unexplained asterisk preserved · `not-brand` VOGUE WORLD kept, not assumed a brand (brand = null, not scored) · `venue_*_null` venue null for that status · `map_coordinates_placeholder_ignored` coordinates exist on the page but are not locations.

## Questions raised in review (resolved by owner approval 2026-11-19)
- Dates under day headings: owner approved all 10 records after review (four-route automated agreement plus a spot-check of the page); the page itself remains the only source.
- Resolved: the 9 ordinary rows are `listed_show_entry` (listed by CNMI; not verified as fashion houses); organizer typing as `schema:Brand` is a documented assumption.
- Resolved: rows whose only missing field is the venue are `confirmed_no_venue`.

Sign-off: owner approved all 10 records and both renames (2026-11-19); recorded in v0.2.1 with a new checksum. v0.1.0 and v0.2.0 are archived.
