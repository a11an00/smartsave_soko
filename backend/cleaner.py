import re
from typing import Tuple, Optional

def parse_volume_and_unit(title: str) -> Tuple[float, str, str]:
    """
    Extracts the weight/volume value and unit from a raw product title.
    Returns: (cleaned_value, cleaned_unit, normalized_brand_or_name)
    """
    # Lowercase for consistent processing
    title_clean = title.lower().strip()
    
    # RegEx pattern to look for patterns like: 1kg, 500g, 2 l, 400ml, 1.5lt
    pattern = r'(\d+(?:\.\d+)?)\s*(kg|g|l|ml|lt|ltr|litres|grams|kilograms)\b'
    match = re.search(pattern, title_clean)
    
    if match:
        value = float(match.group(1))
        unit = match.group(2)
        
        # Standardize unit strings
        if unit in ['kg', 'kilograms']: unit = 'kg'
        elif unit in ['g', 'grams']: unit = 'g'
        elif unit in ['l', 'lt', 'ltr', 'litres']: unit = 'l'
        elif unit in ['ml']: unit = 'ml'
        
        # Remove the size substring from the title to leave a clean name
        clean_name = re.sub(pattern, '', title).strip().replace(" - ", " ").strip()
        return value, unit, clean_name
        
    # Default fallback if no clear weight unit is discovered
    return 1.0, "pcs", title