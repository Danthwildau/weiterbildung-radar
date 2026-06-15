"""
nuts_regions.py — shared NUTS reference + catchment resolution for the
Weiterbildungs-Radar region picker.

The demand data carries nuts_id at three levels:
  level 0 = national (DE)
  level 1 = Bundesland (DE1, DE2, ...)
  level 3 = Landkreis / kreisfreie Stadt (DE111, DE254, ...)

There are NO level-2 (Regierungsbezirk / NUTS-2) rows in the data. NUTS-2 is
used only as a *grouping tier* in the picker: selecting a NUTS-2 region expands
to all NUTS-3 codes sharing its 4-character prefix.

The single source of truth for code <-> name is the demand dataframe itself
(build_lookup_from_demand). The only static table here is NUTS2_NAMES, because
the data has no NUTS-2 rows to derive names from.
"""

# Static NUTS-2 (Regierungsbezirk-Ebene) names — the only thing not derivable
# from the demand data. Source: Eurostat NUTS classification for Germany.
NUTS2_NAMES = {
    "DE11": "Stuttgart", "DE12": "Karlsruhe", "DE13": "Freiburg", "DE14": "Tübingen",
    "DE21": "Oberbayern", "DE22": "Niederbayern", "DE23": "Oberpfalz",
    "DE24": "Oberfranken", "DE25": "Mittelfranken", "DE26": "Unterfranken",
    "DE27": "Schwaben",
    "DE30": "Berlin", "DE40": "Brandenburg", "DE50": "Bremen", "DE60": "Hamburg",
    "DE71": "Darmstadt", "DE72": "Gießen", "DE73": "Kassel",
    "DE80": "Mecklenburg-Vorpommern",
    "DE91": "Braunschweig", "DE92": "Hannover", "DE93": "Lüneburg", "DE94": "Weser-Ems",
    "DEA1": "Düsseldorf", "DEA2": "Köln", "DEA3": "Münster", "DEA4": "Detmold",
    "DEA5": "Arnsberg",
    "DEB1": "Koblenz", "DEB2": "Trier", "DEB3": "Rheinhessen-Pfalz",
    "DEC0": "Saarland",
    "DED2": "Dresden", "DED4": "Chemnitz", "DED5": "Leipzig",
    "DEE0": "Sachsen-Anhalt", "DEF0": "Schleswig-Holstein", "DEG0": "Thüringen",
}

# Default catchment for new users / TH Wildau: three Landkreise + Berlin.
DEFAULT_CATCHMENT = ["DE406", "DE40C", "DE40H", "DE3"]


def build_lookup(demand_df):
    """
    Build code<->name lookups from the demand dataframe (single source of truth).
    Returns a dict with:
      code_to_name : {nuts_id: region_name} for levels 0,1,3
      name_to_code : reverse
      bundeslaender: [(code, name)] sorted, level 1
      landkreise   : [(code, name, nuts2_prefix, bundesland_code)] sorted, level 3
      nuts2        : [(code, name, bundesland_code)] sorted, from NUTS2_NAMES
                     filtered to those actually present in the data
    """
    df = demand_df[["nuts_id", "region", "nuts_level", "bundesland_nuts"]].drop_duplicates()

    # Disambiguate NUTS-3 regions that share an identical display name
    # (e.g. DE251 'Ansbach' the city vs DE256 'Ansbach' the Landkreis). By the
    # German convention the lower-sorted NUTS code is the kreisfreie Stadt and
    # the higher is the Landkreis. We append a clarifying suffix so the two are
    # distinguishable in pickers and tables, while filtering stays on nuts_id.
    lvl3 = df[df["nuts_level"] == 3]
    dup_names = set(lvl3["region"][lvl3["region"].duplicated(keep=False)])
    disambig = {}  # code -> disambiguated display name
    for name in dup_names:
        codes = sorted(str(c) for c in lvl3.loc[lvl3["region"] == name, "nuts_id"])
        # lowest code = kreisfreie Stadt, the rest = Landkreis
        disambig[codes[0]] = f"{name} (kreisfreie Stadt)"
        for c in codes[1:]:
            disambig[c] = f"{name} (Landkreis)"

    code_to_name, name_to_code = {}, {}
    bundeslaender, landkreise = [], []
    for _, r in df.iterrows():
        code = str(r["nuts_id"])
        raw_name = str(r["region"])
        name = disambig.get(code, raw_name)
        code_to_name[code] = name
        name_to_code[name] = code
        if r["nuts_level"] == 1:
            bundeslaender.append((code, name))
        elif r["nuts_level"] == 3:
            bl = str(r["bundesland_nuts"]) if r["bundesland_nuts"] is not None else code[:3]
            landkreise.append((code, name, code[:4], bl))
    bundeslaender.sort(key=lambda x: x[1])
    landkreise.sort(key=lambda x: x[1])

    # NUTS-2 tiers that actually have children in the data
    present_n2 = {c[:4] for c in code_to_name if len(c) == 5}
    nuts2 = []
    for n2_code, n2_name in NUTS2_NAMES.items():
        if n2_code in present_n2:
            nuts2.append((n2_code, n2_name, n2_code[:3]))
    nuts2.sort(key=lambda x: x[1])

    return {
        "code_to_name": code_to_name,
        "name_to_code": name_to_code,
        "bundeslaender": bundeslaender,
        "landkreise": landkreise,
        "nuts2": nuts2,
    }


def resolve_catchment(selected_codes, demand_df, lookup=None):
    """
    Expand a list of selected NUTS codes (any mix of level 1/2/3) into the
    concrete set of NUTS-3 (+ city-state) CODES present in the demand data.

    Returns CODES, not names — because some distinct NUTS-3 regions share a
    display name (e.g. DE251 'Ansbach' the Stadt vs DE256 'Ansbach' the
    Landkreis). Filtering must be on nuts_id, never on the name string.

    - National (DE)  -> ['DE'] (rarely selected).
    - Bundesland (len 3) -> its NUTS-3 children (len-5, first 3 chars match);
      city-states with no children resolve to their own NUTS-3 code if present,
      else their len-3 code.
    - NUTS-2 (len 4) -> NUTS-3 children sharing the 4-char prefix.
    - NUTS-3 (len 5) -> itself.

    Use the returned codes with: demand[demand['nuts_id'].isin(codes)]
    """
    if lookup is None:
        lookup = build_lookup(demand_df)
    code_to_name = lookup["code_to_name"]
    all_codes = list(code_to_name.keys())
    result = set()

    for code in selected_codes:
        code = str(code)
        if len(code) == 5:
            if code in code_to_name:
                result.add(code)
        elif len(code) == 4:  # NUTS-2 -> children
            for c in all_codes:
                if len(c) == 5 and c.startswith(code):
                    result.add(c)
        elif len(code) == 3:  # Bundesland
            children = [c for c in all_codes if len(c) == 5 and c[:3] == code]
            if children:
                result.update(children)
            else:
                # city-state: prefer the NUTS-3 child code if one exists
                child = next((c for c in all_codes
                              if len(c) == 5 and c[:3] == code), None)
                if child:
                    result.add(child)
                elif code in code_to_name:
                    result.add(code)
        elif code in code_to_name:  # national / exact
            result.add(code)

    return sorted(result)


def catchment_label(selected_codes, lookup):
    """Human-readable summary of the current catchment for display."""
    if not selected_codes:
        return "Deutschland"
    parts = []
    c2n = lookup["code_to_name"]
    for code in selected_codes:
        code = str(code)
        if len(code) == 4:
            parts.append(NUTS2_NAMES.get(code, code))
        elif code in c2n:
            parts.append(c2n[code])
        else:
            parts.append(code)
    return ", ".join(parts)
