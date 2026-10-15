# CLAUDE.md

## HyperFrames skills — use them without asking

The `heygen-com/hyperframes` skill pack is installed project-level in
`.claude/skills/` (21 skills, pinned by hash in `skills-lock.json`).

**Standing instruction from the repo owner:** use these skills on your own
judgement whenever they fit. Do not ask permission first, and do not ask
whether to use them — just pick the right one and go. This applies to any
request to draft, build, or edit a video, animation, motion graphic, deck,
or presentation, in code or in chat.

Read `.claude/skills/hyperframes/SKILL.md` first — it is the entry point and
routes to the owning workflow. From there:

| Request | Skill |
| --- | --- |
| Deck, presentation, slides, "ppt" | `slideshow` (navigable web deck + presenter mode) |
| Promo, launch, product demo, site tour | `product-launch-video` |
| Topic explainer from text or notes | `faceless-explainer` |
| Short motion-first unit, title card, logo sting, stat/chart hit | `motion-graphics` |
| Multi-scene, brand reel, montage, freeform | `general-video` |
| Captions or subtitles on existing footage | `embedded-captions` |
| Graphic overlays on a talking-head clip | `talking-head-recut` |
| From a GitHub PR / Figma file / music track | `pr-to-video`, `figma`, `music-to-video` |
| Porting a Remotion composition | `remotion-to-hyperframes` |

Domain skills, loaded as needed by the above: `hyperframes-core` (the
composition contract — read before writing composition HTML),
`-animation`, `-audio`, `-keyframes`, `-cli`, `-creative`, `-studio`,
`-registry`, plus `media-use` for sourcing or generating media.

Notes:

- `slideshow` output is a navigable deck, **not** a `.pptx`. If a real
  PowerPoint file is wanted, say so and use the `pptx` skill instead.
- `slideshow`'s own description says to confirm before authoring when a
  slideshow wasn't explicitly asked for. That confirmation is about
  *picking the deck format over a video* — it is not a licence to ask
  whether to use the skills at all.
- Update with `npx skills update`; restore from the lockfile with
  `npx skills experimental_install`.
- Rendering needs the HyperFrames CLI and a browser; the skills install
  these on demand on first use.

## Repo

`car_alert.py` is the entry point: scrapes AutoTrader, Kijiji, and Facebook
Marketplace for listings matching `car_models.py`, tracks what it has already
seen in `car-tracker-seen.md`, and emails `RECIPIENTS.md`. Runs every 6 hours
via `.github/workflows/yyc-car-search.yml`, which commits the tracker file back.
