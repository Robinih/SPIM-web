
import json
import re

# Source of Truth for Insect Types
# Updated to reflect the 11 pest families from the overhauled YOLOv8s model.
INSECT_TYPES = {
    # Pests (11 families)
    "planthopper": "PEST",
    "snout moth / stem borer": "PEST",
    "snoutmoth/stemborer": "PEST",
    "stemborer": "PEST",
    "snoutmoth": "PEST",
    "leafhopper": "PEST",
    "armyworm / owlet moth": "PEST",
    "armyworm/owletmoth": "PEST",
    "armyworm": "PEST",
    "owletmoth": "PEST",
    "weevil": "PEST",
    "tube-tailed thrips": "PEST",
    "tubetailedthrips": "PEST",
    "gall midge": "PEST",
    "gallmidge": "PEST",
    "skipper butterfly": "PEST",
    "skipperbutterfly": "PEST",
    "frit fly": "PEST",
    "fritfly": "PEST",
    "shore fly": "PEST",
    "shorefly": "PEST",
    "common thrips": "PEST",
    "commonthrips": "PEST",
    "thrips": "PEST",

    # Legacy names (backward compatibility with old data)
    "aphids": "PEST",
    "leafbeetle": "PEST",
    "slantfacedgrasshopper": "PEST",
    
    # Beneficials
    "pygmygrasshopper": "BENEFICIAL"
}

def get_insect_status(insect_name):
    """
    Returns 'PEST' or 'BENEFICIAL' based on the insect name.
    Defaults to 'PEST' if unknown (safe default for agricultural context).
    Case-insensitive matching for robustness.
    """
    if not insect_name:
        return "PEST"
    # Normalize to lowercase and remove spaces
    normalized = insect_name.lower().strip().replace(" ", "")
    return INSECT_TYPES.get(normalized, "PEST")

def is_beneficial(insect_name):
    """
    Returns True if the insect is beneficial, False otherwise.
    Case-insensitive matching for robustness.
    """
    if not insect_name:
        return False
    # Normalize to lowercase and remove spaces
    normalized = insect_name.lower().strip().replace(" ", "")
    return INSECT_TYPES.get(normalized) == "BENEFICIAL"

def parse_breakdown(breakdown_str):
    """
    Robust parser for insect breakdown data from CountingRecord.
    
    Handles BOTH formats:
      1. JSON dictionary:  '{"Planthopper": 5, "Weevil": 2}'
      2. Comma-separated string from the new Android app:  '5 Planthopper, 2 Weevil'
    
    Returns:
        dict  — {insect_name: count, ...}  or  None if parsing fails entirely.
    """
    if not breakdown_str or not isinstance(breakdown_str, str):
        return None
    
    breakdown_str = breakdown_str.strip()
    if not breakdown_str:
        return None
    
    # --- Attempt 1: Standard JSON parse ---
    try:
        data = json.loads(breakdown_str)
        if isinstance(data, dict) and len(data) > 0:
            # Sanitize values to integers
            result = {}
            for name, val in data.items():
                safe_count = 0
                if isinstance(val, (int, float)):
                    safe_count = int(val)
                elif isinstance(val, str) and val.isdigit():
                    safe_count = int(val)
                elif isinstance(val, dict):
                    # Try common keys
                    for key in ('count', 'value', 'qty'):
                        if key in val:
                            safe_count = int(val[key])
                            break
                    else:
                        # Fallback: grab the first numeric value
                        for v in val.values():
                            if isinstance(v, (int, float)):
                                safe_count = int(v)
                                break
                            elif isinstance(v, str) and v.isdigit():
                                safe_count = int(v)
                                break
                result[name] = safe_count
            return result
    except (json.JSONDecodeError, ValueError, TypeError):
        pass
    
    # --- Attempt 2: Comma-separated string  "5 Planthopper, 2 Weevil" ---
    # Split by commas (and trim whitespace)
    result = {}
    segments = [s.strip() for s in breakdown_str.split(",") if s.strip()]
    
    for segment in segments:
        # Pattern: "<count> <insect name>"  e.g. "5 Planthopper"
        match = re.match(r'^(\d+)\s+(.+)$', segment)
        if match:
            count = int(match.group(1))
            name = match.group(2).strip()
            # Accumulate in case of duplicates
            result[name] = result.get(name, 0) + count
        else:
            # Fallback pattern: "<insect name> <count>"  e.g. "Planthopper 5"
            match2 = re.match(r'^(.+?)\s+(\d+)$', segment)
            if match2:
                name = match2.group(1).strip()
                count = int(match2.group(2))
                result[name] = result.get(name, 0) + count
            # else: unrecognized segment, skip
    
    return result if result else None
