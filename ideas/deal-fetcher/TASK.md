# Deal fetcher: offer descriptions + local EDEKA only

**Goal:** Stop wrong deals reaching the deal email. An "XXL Rinder-Hackfleisch (Gut & Günstig)" EDEKA offer from Marktguru for zip 80804 was not in Yagiz's own EDEKA (market 034167, https://www.edeka.de/maerkte/034167/angebote/); in store it turned out to be gemischt.

**Done when:**
- Each offer line in the output also shows Marktguru's `description` text (shortened if long), so wording like "oder gemischt" is visible.
- EDEKA offers only come from EDEKA stores near Yagiz (Scheidplatz, 80804; his market is 034167), not every EDEKA flyer Marktguru merges for the zip. Use whatever store/flyer info Marktguru or edeka.de exposes.
- `data/latest.md` is regenerated with the new output.

**Notes:** Leave REWE, PENNY, Lidl, ALDI SÜD as they are. Delete this TASK.md in your final commit.
