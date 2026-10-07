
from utils.helpers import namespaces
from utils.getter_utils import get_attribute_with_ns
from utils.common_utils import create_sub_element

from lxml import etree

def get_action_element_class(action):
    """
    Determines the MagicDraw element class for a given action based on its type.
    """
    action_type = action.get("type")
    if action_type in ["CallBehaviorAction", "CallOperationAction", "OpaqueAction"]:
        return action_type
    elif action_type.startswith("Accept") or action_type.startswith("Send"):
        return "SignalAction"
    return "Action"

def get_node_element_class(node):
    """
    Determines the MagicDraw element class for a given activity node based on its nodeType.
    """
    node_type = node.get("nodeType")
    if node_type in ["InitialNode", "ActivityFinalNode", "FlowFinalNode"]:
        return "PseudoNode"
    elif node_type in ["CentralBufferNode", "DataStoreNode", "ActivityParameterNode"]:
        return "ObjectNode"
    elif node_type in ["DecisionNode", "MergeNode"]:
        return "Decision"
    elif node_type in ["ForkNode", "JoinNode"]:
        return "Bar"
    return node_type

def update_act_geometry(root):
    """
    Updates the geometry of nodes, swimlanes, and other elements in a MagicDraw Activity Diagram.

    Args:
        root (etree.Element): The MagicDraw filePart node representing the Activity Diagram.
    """
    # --- Configuration & Initialization ---
    START_Y = 200
    START_X = 150
    CELL_WIDTH = 350
    HEADER_HEIGHT = 40
    Y_STEP = 80
    
    nodes = {}
    edges = []
    node_to_cell = {}
    cells = []
    headers = []
    floating_elements = []
    
    ignore_classes = {
        "Swimlane", "SwimlaneCell", "SwimlaneHeader", "DiagramFrame", "ObjectFlow",
        "ControlFlow", "Pin", "NoteAnchor", "InterruptibleActivityRegion", "InterruptibeActivityRegion"
    }
    
    # Helper: Force MagicDraw to snap pins to specific borders (0=Top, 2=Bottom)
    def set_pin_edge(pin_elem, edge_val):
        edge = pin_elem.find('edge')
        if edge is not None:
            pin_elem.remove(edge)
        create_sub_element(pin_elem, "edge", attrib={
            etree.QName(namespaces["xmi"], "value"): str(edge_val)
        })

    # --- Step 1: Parse Swimlanes and map elements to their parent cells ---
    swimlanes = root.findall('.//mdElement[@elementClass="Swimlane"]')
    for swimlane in swimlanes:
        sw_cells = swimlane.findall('.//mdElement[@elementClass="SwimlaneCell"]')
        sw_headers = swimlane.findall('.//mdElement[@elementClass="SwimlaneHeader"]')
        
        start_idx = len(cells)
        for i, cell in enumerate(sw_cells):
            cells.append(cell)
            cell_idx = start_idx + i
            for view in cell.findall('.//mdOwnedViews/mdElement'):
                xmi_id = get_attribute_with_ns("id", view)
                if xmi_id:
                    node_to_cell[xmi_id] = cell_idx
        
        for header in sw_headers:
            headers.append(header)

    default_cell_idx = len(cells) if len(cells) > 0 else 0

    # --- Step 2: Gather nodes, flow edges, and floating annotations ---
    for elem in root.findall('.//mdElement'):
        cls = elem.get('elementClass')
        is_node = cls in ["Bar", "Decision"] or \
                  (cls and any(cls.endswith(suffix) for suffix in ["Node", "Action"]))
                  
        if is_node:
            xmi_id = get_attribute_with_ns("id", elem)
            if xmi_id:
                nodes[xmi_id] = elem
        elif cls in {"ObjectFlow", "ControlFlow"}:
            src_elem = elem.find('linkFirstEndID')
            tgt_elem = elem.find('linkSecondEndID')
            if src_elem is not None and tgt_elem is not None:
                src = get_attribute_with_ns("idref", src_elem)
                tgt = get_attribute_with_ns("idref", tgt_elem)
                if src and tgt:
                    edges.append((src, tgt))
        elif cls not in ignore_classes:
            geom = elem.find('geometry')
            if geom is not None and geom.text and ',' in geom.text and ';' not in geom.text:
                floating_elements.append(elem)
                    
    if not nodes:
        return

    # --- Step 3: Determine vertical order (Topological layers) ---
    layers = {nid: 0 for nid in nodes}
    for _ in range(len(nodes)):
        changed = False
        for src, tgt in edges:
            if src in layers and tgt in layers:
                if layers[tgt] <= layers[src]:
                    layers[tgt] = layers[src] + 1
                    changed = True
        if not changed:
            break 

    # --- Step 4: Optimize horizontal Swimlane order based on flow connectivity ---
    num_cells = len(cells)
    if num_cells > 0:
        cell_weights = {i: {} for i in range(num_cells)}
        for src, tgt in edges:
            u = node_to_cell.get(src)
            v = node_to_cell.get(tgt)
            if u is not None and v is not None and u != v and u != default_cell_idx and v != default_cell_idx:
                cell_weights[u][v] = cell_weights[u].get(v, 0) + 1
                cell_weights[v][u] = cell_weights[v].get(u, 0) + 1

        cell_min_layer = {i: float('inf') for i in range(num_cells)}
        for nid in nodes:
            c = node_to_cell.get(nid)
            if c is not None and c != default_cell_idx:
                cell_min_layer[c] = min(cell_min_layer[c], layers.get(nid, float('inf')))

        unplaced = set(range(num_cells))
        sorted_cell_indices = []

        while unplaced:
            if not sorted_cell_indices:
                nxt = min(unplaced, key=lambda c: (cell_min_layer[c], c))
            else:
                last_cell = sorted_cell_indices[-1]
                neighbors = [(n, cell_weights[last_cell][n]) for n in unplaced if n in cell_weights[last_cell]]
                if neighbors:
                    # Pick most connected neighbor; tie-break by smallest topological layer
                    nxt = max(neighbors, key=lambda x: (x[1], -cell_min_layer[x[0]]))[0]
                else:
                    nxt = min(unplaced, key=lambda c: (cell_min_layer[c], c))
            
            sorted_cell_indices.append(nxt)
            unplaced.remove(nxt)

        cell_visual_order = {old_idx: visual_idx for visual_idx, old_idx in enumerate(sorted_cell_indices)}
    else:
        cell_visual_order = {}
        
    cell_visual_order[default_cell_idx] = num_cells

    # --- Step 5: Resolve grid overlaps (shift nodes down if slot is taken) ---
    occupied = set() 
    sorted_nodes = sorted(nodes.keys(), key=lambda n: layers[n])
    
    final_layers = {}
    for nid in sorted_nodes:
        layer = layers[nid]
        old_cell_idx = node_to_cell.get(nid, default_cell_idx)
        visual_cell_idx = cell_visual_order.get(old_cell_idx, old_cell_idx)
        
        while (visual_cell_idx, layer) in occupied:
            layer += 1
        occupied.add((visual_cell_idx, layer))
        final_layers[nid] = layer
        
    max_layer = max(final_layers.values()) if final_layers else 0
    
    # --- Step 6: Apply geometries to Nodes and auto-distribute Pins ---
    for nid, elem in nodes.items():
        layer = final_layers[nid]
        old_cell_idx = node_to_cell.get(nid, default_cell_idx)
        visual_cell_idx = cell_visual_order.get(old_cell_idx, old_cell_idx)
        
        y = START_Y + HEADER_HEIGHT + 20 + layer * Y_STEP
        
        geom = elem.find('geometry')
        if geom is None:
            geom = create_sub_element(elem, 'geometry')
            
        pins = elem.findall('.//mdOwnedViews/mdElement[@elementClass="Pin"]')
        if pins:
            in_pins, out_pins = [], []
            for p in pins:
                el_id = p.find('elementID')
                if el_id is not None:
                    ref = get_attribute_with_ns("idref", el_id) or ""
                    if 'out' in ref.lower():
                        out_pins.append(p)
                    else:
                        in_pins.append(p)
                else:
                    in_pins.append(p)

            # Dynamically scale node width to accommodate all pins
            max_pins_on_edge = max(len(in_pins), len(out_pins))
            NODE_W = max(120, (max_pins_on_edge * 25) + 20)
            NODE_H = 50
            
            x = START_X + visual_cell_idx * CELL_WIDTH + (CELL_WIDTH // 2) - (NODE_W // 2)
            geom.text = f"{x}, {y}, {NODE_W}, {NODE_H}"

            in_spacing = NODE_W / (len(in_pins) + 1) if in_pins else 0
            for i, p in enumerate(in_pins):
                p_geom = p.find('geometry')
                if p_geom is None:
                    p_geom = create_sub_element(p, 'geometry')
                px = x + int((i + 1) * in_spacing) - 8
                py = y - 8
                p_geom.text = f"{px}, {py}, 16, 16"
                set_pin_edge(p, 0)

            out_spacing = NODE_W / (len(out_pins) + 1) if out_pins else 0
            for i, p in enumerate(out_pins):
                p_geom = p.find('geometry')
                if p_geom is None:
                    p_geom = create_sub_element(p, 'geometry')
                px = x + int((i + 1) * out_spacing) - 8
                py = y + NODE_H - 8
                p_geom.text = f"{px}, {py}, 16, 16"
                set_pin_edge(p, 2)
        else:
            NODE_W = 120
            x = START_X + visual_cell_idx * CELL_WIDTH + (CELL_WIDTH // 2) - (NODE_W // 2)
            geom.text = f"{x}, {y}, 0, 0"
        
    # --- Step 7: Size and position Swimlane containers (Headers, Cells, Swimlanes) ---
    total_cell_height = (max_layer + 2) * Y_STEP
    total_swimlane_height = HEADER_HEIGHT + total_cell_height

    for idx, cell in enumerate(cells):
        visual_idx = cell_visual_order.get(idx, idx)
        x = START_X + visual_idx * CELL_WIDTH
        y = START_Y + HEADER_HEIGHT
        
        geom = cell.find('geometry')
        if geom is None:
            geom = create_sub_element(cell, 'geometry')
        geom.text = f"{x}, {y}, {CELL_WIDTH}, {total_cell_height}"
        
    for idx, header in enumerate(headers):
        col_idx = idx if idx < len(cells) else len(cells) - 1
        visual_idx = cell_visual_order.get(col_idx, col_idx)
        x = START_X + visual_idx * CELL_WIDTH
        y = START_Y
        
        geom = header.find('geometry')
        if geom is None:
            geom = create_sub_element(header, 'geometry')
        geom.text = f"{x}, {y}, {CELL_WIDTH}, {HEADER_HEIGHT}"

    for swimlane in swimlanes:
        x = START_X
        y = START_Y
        w = max(len(cells), 1) * CELL_WIDTH
        h = total_swimlane_height
        
        geom = swimlane.find('geometry')
        if geom is None:
            geom = create_sub_element(swimlane, 'geometry')
        geom.text = f"{x}, {y}, {w}, {h}"

    # --- Step 8: Layout floating elements (Comments, Notes) beneath the swimlanes ---
    float_y = START_Y + total_swimlane_height + 50
    float_x = START_X
    
    max_columns = max(len(cells), 1)
    if default_cell_idx > len(cells) - 1 and len(cells) > 0:
        max_columns += 1 
    max_grid_width = START_X + (max_columns * CELL_WIDTH)
    
    row_max_h = 50
    
    for elem in floating_elements:
        geom = elem.find('geometry')
        w, h = 150, 50
        
        if geom is not None and geom.text:
            parts = [p.strip() for p in geom.text.split(',')]
            if len(parts) >= 4:
                try:
                    w = int(parts[2]) if int(parts[2]) > 0 else 150
                    h = int(parts[3]) if int(parts[3]) > 0 else 50
                except ValueError:
                    pass
        else:
            if geom is None:
                geom = create_sub_element(elem, 'geometry')

        geom.text = f"{float_x}, {float_y}, {w}, {h}"
        
        row_max_h = max(row_max_h, h)
        float_x += w + 30
        
        if float_x > max_grid_width - 150:
            float_x = START_X
            float_y += row_max_h + 30
            row_max_h = 50

    # --- Step 9: Wrap InterruptibleActivityRegions around their internal children ---
    regions = root.findall('.//mdElement[@elementClass="InterruptibleActivityRegion"]')
    if not regions:
        regions = root.findall('.//mdElement[@elementClass="InterruptibeActivityRegion"]')
        
    for region in regions:
        min_x, min_y = float('inf'), float('inf')
        max_x, max_y = float('-inf'), float('-inf')
        
        for child in region.findall('.//mdElement'):
            geom = child.find('geometry')
            if geom is not None and geom.text:
                if ';' in geom.text:
                    parts = [p.strip() for p in geom.text.replace(';', ',').split(',') if p.strip()]
                    for i in range(0, len(parts)-1, 2):
                        try:
                            cx, cy = int(parts[i]), int(parts[i+1])
                            min_x = min(min_x, cx)
                            min_y = min(min_y, cy)
                            max_x = max(max_x, cx)
                            max_y = max(max_y, cy)
                        except ValueError:
                            pass
                else:
                    parts = [p.strip() for p in geom.text.split(',')]
                    if len(parts) >= 2:
                        try:
                            cx, cy = int(parts[0]), int(parts[1])
                            cw = int(parts[2]) if len(parts) >= 4 and int(parts[2]) > 0 else 0
                            ch = int(parts[3]) if len(parts) >= 4 and int(parts[3]) > 0 else 0
                            min_x = min(min_x, cx)
                            min_y = min(min_y, cy)
                            max_x = max(max_x, cx + cw)
                            max_y = max(max_y, cy + ch)
                        except ValueError:
                            pass
        
        geom = region.find('geometry')
        if geom is None:
            geom = create_sub_element(region, 'geometry')
            
        if min_x != float('inf'):
            pad = 20
            rx = min_x - pad
            ry = min_y - pad
            rw = (max_x - min_x) + (pad * 2)
            rh = (max_y - min_y) + (pad * 2)
            geom.text = f"{rx}, {ry}, {rw}, {rh}"
        else:
            geom.text = f"{START_X}, {START_Y}, 200, 100"

    # --- Step 10: Update the overarching DiagramFrame to enclose everything ---
    frame = root.find('.//mdElement[@elementClass="DiagramFrame"]')
    if frame is not None:
        geom = frame.find('geometry')
        if geom is None:
            geom = create_sub_element(frame, 'geometry')
            
        final_frame_h = max(START_Y + total_swimlane_height, float_y + row_max_h) + 50
        max_frame_x = START_X + max_columns * CELL_WIDTH + 150
        
        for region in regions:
            r_geom = region.find('geometry')
            if r_geom is not None and r_geom.text:
                parts = [p.strip() for p in r_geom.text.split(',')]
                if len(parts) >= 4:
                    try:
                        rx, ry, rw, rh = int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3])
                        max_frame_x = max(max_frame_x, rx + rw + 50)
                        final_frame_h = max(final_frame_h, ry + rh + 50)
                    except ValueError:
                        pass
                        
        geom.text = f"5, 5, {max_frame_x}, {final_frame_h}"