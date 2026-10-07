
import re
import html

# Define namespaces for easier parsing using XPath
namespaces = {
    "xmi": "http://www.omg.org/spec/XMI/20131001",
    "uml": "http://www.omg.org/spec/UML/20131001",
    "sysml": "http://www.omg.org/spec/SysML/20181001/SysML",
    "xsi": "http://www.w3.org/2001/XMLSchema-instance",
}
# The same XMI file may use different namespaces, so we define an alternative set. Add more if needed.
alt_namespaces = {
    "xmi": "http://www.omg.org/XMI"
}
all_ns = [namespaces]
for key, value in alt_namespaces.items():
    new_ns = namespaces.copy()
    new_ns[key] = value
    if new_ns not in all_ns:
        all_ns.append(new_ns)

def smart_cast(value):
    """
    Attempts to convert a value to an integer or float if possible, otherwise returns the original value.
    """
    if isinstance(value, str):
        lower_val = value.strip().lower()
        if lower_val == "true":
            return True
        if lower_val == "false":
            return False
    try:
        return int(value)
    except:
        try:
            return float(value)
        except:
            return value
        
def remove_html_tags(text):
    """
    Removes HTML tags, unescapes HTML entities, and collapses successive whitespace into a single space.
    """
    if not isinstance(text, str):
        return ""
    cleaned_text = re.sub(r'<.*?>', '', text)
    cleaned_text = html.unescape(cleaned_text)
    cleaned_text = re.sub(r'\s+', ' ', cleaned_text)
    cleaned_text = re.sub(r"\w+\s*\{[^}]*\}", "", cleaned_text)
    return cleaned_text.strip()

def reorder_dict(data: dict, first_keys: list[str] = None, last_keys: list[str] = None) -> dict:
    """
    Return a new dict where:
      - keys in `first_keys` appear first (in the given order)
      - keys in `last_keys` appear last (in the given order)
      - all other keys keep their original relative order in between
    """
    first_keys = first_keys or []
    last_keys = last_keys or []

    # Build the new dictionary in order
    return {
        **{k: data[k] for k in first_keys if k in data},
        **{k: v for k, v in data.items() if k not in first_keys and k not in last_keys},
        **{k: data[k] for k in last_keys if k in data},
    }

def is_inside(rect1, rect2):
    """
    Check if rectangle `rect1` is completely inside rectangle `rect2`.

    Each rectangle is represented as a dict with two fields:
      - "A_Coordinates": [x, y] (any corner)
      - "B_Coordinates": [x, y] (opposite diagonal corner)

    The function automatically normalizes the corners, so it works
    regardless of which corners are labeled A or B.

    Returns:
        bool: True if rect1 lies entirely within rect2, False otherwise.
    """
    # Normalize rect1
    ax1, ay1 = rect1["A_Coordinates"]
    ax2, ay2 = rect1["B_Coordinates"]
    ax_min, ax_max = min(ax1, ax2), max(ax1, ax2)
    ay_min, ay_max = min(ay1, ay2), max(ay1, ay2)

    # Normalize rect2
    bx1, by1 = rect2["A_Coordinates"]
    bx2, by2 = rect2["B_Coordinates"]
    bx_min, bx_max = min(bx1, bx2), max(bx1, bx2)
    by_min, by_max = min(by1, by2), max(by1, by2)

    # Check if rect1 is inside rect2
    return (bx_min <= ax_min and bx_max >= ax_max and
            by_min <= ay_min and by_max >= ay_max)
