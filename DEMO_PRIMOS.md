# Primo's Pizza demo — spec to shareable pack, one command

The Deli Counter showcase building (specs docs: deli_counter/specs/
primos_pizza.NOTES.md) staged as a one-building site. Everything is
validated green (DC check + combat_audit --rules all + site_audit + gates
+ pacing); the only thing the sandbox can't do is run Blender, so cutting
the real pack is one command on a machine with it:

    cd C:\Projects\lot
    python cater.py specs\primos_demo.json C:\Users\Brannen\Documents\dd-primos-demo --package --note "Primo's PoC v0.1.0"

That builds primos_pizza.glb, assembles the lit walkable site, runs every
gate + audit, and cuts dist\primos_demo_pack_v0.1.0.zip -- glb + portable
scenes + gameplay contract + provenance manifest + self-contained QA walk.
Send the zip; a collaborator opens site tscn or F6s the walk with zero
installs.

Preview without Blender (boxes): add --preview.

First-walk checklist (from the NOTES): dumbwaiter climb kitchen->count
room, roof loop (ladder up, hatch drop), bag-carry feel on the alley
route, first slice from the count door.
