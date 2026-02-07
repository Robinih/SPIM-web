
# Source of Truth for Insect Types
INSECT_TYPES = {
    # Pests
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
