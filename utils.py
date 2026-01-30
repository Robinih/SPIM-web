
# Source of Truth for Insect Types
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
    Defaults to 'PEST' if unknown (safe default for agricultural context, 
    but logic can be adjusted).
    """
    return INSECT_TYPES.get(insect_name, "PEST")

def is_beneficial(insect_name):
    """
    Returns True if the insect is beneficial, False otherwise.
    """
    return INSECT_TYPES.get(insect_name) == "BENEFICIAL"
