"""
Generate manual verification guidance for species requiring further research.
"""

import csv
from pathlib import Path

# Define paths
OUTPUT_DIR = Path(__file__).parent.parent / "outputs" / "next_dutch_firsts"

manual_review_species = {
    # Atlantic Pathway - Nearctic Species
    "Black-and-white Warbler": {
        "pathway": "Atlantic",
        "region": "North America",
        "research_priority": "MEDIUM",
        "notes": "Nearctic migrant with established western European vagrancy pattern. Check for rare but documented Dutch records.",
        "sources": [
            "Dutch Avifauna database - search for 'Gestreepte Zanger' or scientific name",
            "CDNA bulletins 2015-2025",
            "Vogelbescherming species account",
            "waarnemingen.nl filter by species",
        ],
    },
    "Black-billed Cuckoo": {
        "pathway": "Atlantic",
        "region": "North America",
        "research_priority": "MEDIUM",
        "notes": "Candidate status needs verification against recent Dutch decisions. Closely related to Yellow-billed Cuckoo (verified 1 record).",
        "sources": [
            "CSNA Dutch checklist status",
            "CDNA bulletins post-2024",
            "Recent rarity reports comparison with Yellow-billed Cuckoo",
        ],
    },
    "Black-throated Gray Warbler": {
        "pathway": "Atlantic",
        "region": "North America",
        "research_priority": "HIGH",
        "notes": "High interest: western Nearctic warbler with potential for Atlantic vagrancy. Rare but expected vagrant.",
        "sources": [
            "Dutch Avifauna - search 'Zwartkeelgrasmus' or similar",
            "CDNA archives for recent records",
            "Western European rarity databases (UK, Belgium, Germany)",
            "Species-specific rarity report search",
        ],
    },
    "Blue Grosbeak": {
        "pathway": "Atlantic",
        "region": "North America",
        "research_priority": "MEDIUM",
        "notes": "Transatlantic candidate; provenance should be carefully assessed for any Dutch records. Search for both North American and Caribbean subspecies.",
        "sources": [
            "Dutch Avifauna database",
            "CDNA records by subspecies",
            "Provenance assessment literature",
        ],
    },
    "Brewer's Sparrow": {
        "pathway": "Atlantic",
        "region": "North America",
        "research_priority": "MEDIUM",
        "notes": "Speculative western Nearctic candidate; identification and provenance require care. Check field identification issues.",
        "sources": [
            "Dutch Avifauna rarity section",
            "CDNA identification criteria documents",
            "European records and identification papers",
        ],
    },
    "Cassin's Sparrow": {
        "pathway": "Atlantic",
        "region": "North America",
        "research_priority": "MEDIUM",
        "notes": "Speculative candidate; western European vagrancy evidence needs review. Very rare in Europe.",
        "sources": [
            "European bird records database (EBCC)",
            "Dutch Avifauna - check rarity section",
            "CDNA for any documented Dutch records",
        ],
    },
    "Cedar Waxwing": {
        "pathway": "Atlantic",
        "region": "North America",
        "research_priority": "LOW",
        "notes": "Potential long-distance vagrant; provenance should be assessed. Irruptive species - check for wandering population records.",
        "sources": [
            "Dutch Avifauna - search 'Zijdestaart' (Dutch name)",
            "CDNA post-2010 records",
            "Irruption event documentation",
        ],
    },
    "Common Nighthawk": {
        "pathway": "Atlantic",
        "region": "North America",
        "research_priority": "HIGH",
        "notes": "High interest: long-distance nocturnal migrant with precedent in western Europe. May have documented records.",
        "sources": [
            "Dutch Avifauna - nocturnal migrant database",
            "CDNA bulletins search",
            "Recent seawatch/nocturnal migration records",
            "Published transatlantic migration studies",
        ],
    },
    "MacGillivray's Warbler": {
        "pathway": "Atlantic",
        "region": "North America",
        "research_priority": "MEDIUM",
        "notes": "Western Nearctic migrant; similar species and identification should be reviewed. Watch for misidentifications.",
        "sources": [
            "Dutch Avifauna with identification notes",
            "CDNA field guide comparisons",
            "Confusion species documentation (Connecticut Warbler, etc.)",
        ],
    },
    "Swainson's Hawk": {
        "pathway": "Atlantic",
        "region": "North America",
        "research_priority": "MEDIUM",
        "notes": "Long-distance migrant; an exceptional long-range raptor candidate. Check for vagrant records.",
        "sources": [
            "Dutch Avifauna - raptor section",
            "CDNA records for long-distance raptors",
            "Published raptor vagrancy studies",
        ],
    },
    "Summer Tanager": {
        "pathway": "Atlantic",
        "region": "North America",
        "research_priority": "MEDIUM",
        "notes": "Nearctic migrant; potential transatlantic vagrant. Check for color morph variants.",
        "sources": [
            "Dutch Avifauna database",
            "CDNA tanager records",
            "Western European rarity compilations",
        ],
    },
    "Townsend's Warbler": {
        "pathway": "Atlantic",
        "region": "North America",
        "research_priority": "MEDIUM",
        "notes": "High interest: western Nearctic warbler with potential for Atlantic vagrancy. Check for vagrant records.",
        "sources": [
            "Dutch Avifauna - western warbler section",
            "CDNA bulletins",
            "Western North American origin records",
        ],
    },
    
    # Atlantic Pathway - Rails
    "Virginia Rail": {
        "pathway": "Atlantic",
        "region": "North America",
        "research_priority": "MEDIUM",
        "notes": "Secretive wetland bird; detection and origin are challenging. May have unrecorded or under-recorded presence.",
        "sources": [
            "Dutch Avifauna - wetland rarity section",
            "CDNA secretive species records",
            "Recent wetland survey data",
            "Migrant detection program results",
        ],
    },
    "Yellow Rail": {
        "pathway": "Atlantic",
        "region": "North America",
        "research_priority": "MEDIUM",
        "notes": "Secretive wetland migrant; detection and origin are challenging. May have unrecorded presence.",
        "sources": [
            "Dutch Avifauna - rail species records",
            "CDNA call playback survey results",
            "Recent migration monitoring data",
            "European Rail Census participation",
        ],
    },
    
    # Eastern Pathway - Asian/Siberian Species
    "Eastern Buzzard": {
        "pathway": "Eastern",
        "region": "East Asia",
        "research_priority": "MEDIUM",
        "notes": "Speculative eastern raptor candidate; identification and taxonomic treatment need review. May be confused with Common Buzzard.",
        "sources": [
            "Dutch Avifauna - Eastern raptor section",
            "CDNA raptor field identification guides",
            "Recent taxonomy updates (IOC/IOSNT)",
            "Eastern raptor vagrancy documentation",
        ],
    },
    "Japanese Robin": {
        "pathway": "Eastern",
        "region": "East Asia",
        "research_priority": "HIGH",
        "notes": "Speculative long-distance candidate; provenance should be assessed. Eastern Asian forest species.",
        "sources": [
            "Dutch Avifauna - eastern robin section",
            "CDNA East Asian species records",
            "Recent European records documentation",
            "Captive bird origin assessment (garden species in collections)",
        ],
    },
    "Mugimaki Flycatcher": {
        "pathway": "Eastern",
        "region": "East Asia",
        "research_priority": "HIGH",
        "notes": "High interest: migratory East Asian flycatcher and potential western vagrant. May have recent Dutch records.",
        "sources": [
            "Dutch Avifauna database",
            "CDNA post-2015 bulletins",
            "Eastern Palearctic migratory flyway documentation",
            "Recent Western European records compilation",
        ],
    },
    "Pale Thrush": {
        "pathway": "Eastern",
        "region": "East Asia",
        "research_priority": "HIGH",
        "notes": "High interest: East Asian thrush and potential western vagrant. May have vagrant documentation.",
        "sources": [
            "Dutch Avifauna - Eastern thrush section",
            "CDNA records by subspecies",
            "Recent European sighting compilations",
            "Migration pattern documentation",
        ],
    },
    "Rufous-tailed Robin": {
        "pathway": "Eastern",
        "region": "East Asia",
        "research_priority": "MEDIUM",
        "notes": "Asian migrant; difficult detection and identification. May have unrecorded presence or confusion with related species.",
        "sources": [
            "Dutch Avifauna - Asian robin section",
            "CDNA identification criteria",
            "Confusion species comparison (e.g., Red-flanked Bluetail)",
            "European records database",
        ],
    },
    "Siberian Blue Robin": {
        "pathway": "Eastern",
        "region": "East Asia",
        "research_priority": "MEDIUM",
        "notes": "Asian migrant; potential long-distance vagrant. Check for vagrant records.",
        "sources": [
            "Dutch Avifauna database",
            "CDNA blue robin records",
            "Recent European sighting records",
        ],
    },
    "Thick-billed Warbler": {
        "pathway": "Eastern",
        "region": "East Asia",
        "research_priority": "HIGH",
        "notes": "High interest: Asian long-distance migrant; recent Dutch status needs verification. Check post-2020 records.",
        "sources": [
            "Dutch Avifauna - Asian warbler section",
            "CDNA bulletins 2020-2025",
            "Recent rarity report compilations",
            "Taxonomy updates (may have been split into multiple species)",
        ],
    },
}

def generate_manual_verification_guide():
    """Generate detailed guide for manual verification of flagged species."""
    
    output = []
    output.append("# Manual Verification Guidance\n")
    output.append("## Species Requiring Further Research\n")
    output.append(f"**Total species requiring manual verification: {len(manual_review_species)}**\n")
    output.append("**Process:** Research using authoritative Dutch sources (Dutch Avifauna, CDNA, recent publications)\n\n")
    
    # Group by priority
    high_priority = []
    medium_priority = []
    low_priority = []
    
    for species, data in sorted(manual_review_species.items()):
        if data['research_priority'] == 'HIGH':
            high_priority.append((species, data))
        elif data['research_priority'] == 'MEDIUM':
            medium_priority.append((species, data))
        else:
            low_priority.append((species, data))
    
    # Generate by priority
    output.append("---\n")
    output.append(f"## HIGH PRIORITY ({len(high_priority)} species)\n")
    output.append("These species are most likely to have Dutch records or represent high-value candidates.\n\n")
    
    for species, data in high_priority:
        output.append(generate_species_entry(species, data))
    
    output.append("\n---\n")
    output.append(f"## MEDIUM PRIORITY ({len(medium_priority)} species)\n")
    output.append("These species require verification but are lower likelihood.\n\n")
    
    for species, data in medium_priority:
        output.append(generate_species_entry(species, data))
    
    if low_priority:
        output.append("\n---\n")
        output.append(f"## LOW PRIORITY ({len(low_priority)} species)\n")
        output.append("These species are unlikely to have Dutch records but warrant checking.\n\n")
        
        for species, data in low_priority:
            output.append(generate_species_entry(species, data))
    
    # Research template
    output.append("\n---\n")
    output.append("## Research Template\n\n")
    output.append("""### For Each Species:

1. **Dutch Avifauna Database Query**
   - Visit: https://www.dutchavifauna.nl/
   - Search by common name and scientific name
   - Record any findings with years and locations
   - Note source (published checklist vs. observation database)

2. **CDNA Records Check**
   - Commissie Dwaalgasten Nederlandse Avifauna
   - Search accepted/rejected records database
   - Check species accounts and decision documents
   - Note rare-birds-committee status

3. **Recent Publications**
   - Search Vogelbescherming species accounts
   - Check recent rarity reports (last 5 years)
   - Review published field guides for Dutch records
   - Look for subspecific identification notes

4. **Occurrence Database**
   - Query waarnemingen.nl for observations
   - Filter by date range and reliability
   - Note observation frequency (single vs. multiple)
   - Assess data recency and quality

5. **Taxonomy & Identification**
   - Verify current IOC/IOSNT taxonomy
   - Check for recent splits affecting species ID
   - Note any subspecific considerations
   - Document any identification controversies

### Record Entry Fields:

- **Species:** [Common name]
- **Scientific Name:** [if different from master list]
- **Record Count:** [number of documented records]
- **Date Range:** [first year - last year]
- **Locations:** [where recorded in Netherlands]
- **Source:** [CDNA accepted, Dutch Avifauna, Vogelbescherming, etc.]
- **Confidence:** [high, medium, low]
- **Notes:** [identification issues, origin assessment, taxonomy]
- **URLs/References:** [links to source documents]
""")
    
    return "".join(output)

def generate_species_entry(species: str, data: dict) -> str:
    """Generate a detailed entry for a species."""
    entry = []
    entry.append(f"### {species}\n")
    entry.append(f"**Pathway:** {data['pathway']} | **Region:** {data['region']} | **Priority:** {data['research_priority']}\n\n")
    entry.append(f"**Research Note:**  \n{data['notes']}\n\n")
    entry.append("**Recommended Sources:**\n")
    for source in data['sources']:
        entry.append(f"- {source}\n")
    entry.append("\n")
    return "".join(entry)

# Generate and save
guide = generate_manual_verification_guide()

guide_path = OUTPUT_DIR / "MANUAL_VERIFICATION_GUIDANCE.md"
with open(guide_path, 'w', encoding='utf-8') as f:
    f.write(guide)

print(f"✓ Generated manual verification guide: {guide_path}")
print(f"  - HIGH priority: {len([s for s, d in manual_review_species.items() if d['research_priority'] == 'HIGH'])}")
print(f"  - MEDIUM priority: {len([s for s, d in manual_review_species.items() if d['research_priority'] == 'MEDIUM'])}")
print(f"  - LOW priority: {len([s for s, d in manual_review_species.items() if d['research_priority'] == 'LOW'])}")
