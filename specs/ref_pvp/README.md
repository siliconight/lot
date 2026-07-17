# ref_pvp_site — the reference pvp_heist mission site

The Phase 0 reference site: 3 building placements (bank_job staged twice at
different transforms + the pvp reference station), pvp_heist site gates, a
road, courtyard, cover, perimeter, and attacker staging / extraction site
markers.

`buildings/` is NOT committed — it holds built Deli Counter outputs. To
populate it:

    cd ../../..                           # gabagool_factory root
    python deli_counter/build.py deli_counter/specs/pvp_station_ref.json
    python deli_counter/build.py deli_counter/specs/bank_job.json
    # copy the four outputs here:
    #   pvp_station_ref.glb + .gameplay.json
    #   bank_job.glb        + .gameplay.json

Then assemble:

    python lot.py specs/ref_pvp/ref_pvp_site.json --walkable --navqa
