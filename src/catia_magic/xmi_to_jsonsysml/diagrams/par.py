
from diagrams.ibd import extract_ibd

def extract_par(diagram):
    """
    Extracts a SysML Parametric Diagram from the XMI file and converts it to Json-SysML.

    Args:
        diagram (Element): The XML element representing the SysML Parametric Diagram.

    Returns:
        par (dict): A dictionary representing the SysML Parametric Diagram in Json-SysML format.
    """
    
    par = extract_ibd(diagram)
    par["diagramType"] = "par"

    return par