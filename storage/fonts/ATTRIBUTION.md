## Font Attribution (Google Fonts — SIL Open Font License)

All fonts are downloaded from Google Fonts and are subject to the SIL Open Font License (OFL). They are embedded locally for animated caption rendering via libass (`fontsdir`). No external network access occurs at render time.

### Font files in `storage/fonts/`:

| Font | Weight/Style | Size |
|---|---|---|
| **Montserrat** | Regular (400), ExtraBold (800) | 183 KB + 745 KB (variable) |
| **Poppins** | Regular (400), SemiBold (600) | 160 KB + 157 KB |
| **Bebas Neue** | Regular (400) | 61 KB |

### License

- The SIL Open Font License is available at: https://github.com/google/fonts/blob/main/ofl/montserrat OFL.txt, ofl/poppins OFL.txt, ofl/bebasneue OFL.txt.
- You may use, modify, and redistribute the fonts freely, but you must not sell them on their own. If you redistribute, include the original license and keep the font names unchanged (or rename if modified).

### How they are used

- `settings.fonts_dir` (default: `storage/fonts/`) is passed to FFmpeg's `ass` filter as `:fontsdir=...`.
- Each rendered clip's ASS subtitles use the selected `caption_preset` font from this collection.
- No API keys or external calls are required at render time.