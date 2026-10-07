
from utils.getter_utils import get_attribute_with_ns
from utils.common_utils import create_sub_element

def update_sd_geometry(root):
    START_Y = 150
    GAP = 30
    MSG_HEIGHT = 42
    LIFELINE_START_X = 28
    LIFELINE_SPACING = 250
    FRAG_X = 49
    FRAG_WIDTH = 364
    MSG_X = 56
    MSG_WIDTH = 350

    current_y = START_Y
    fragment_mid_y = {}
    
    # Pre-map fragments to the Y-coordinate of the message pointing to them
    fragment_target_y = {}
    messages = root.findall('.//mdElement[@elementClass="SeqMessage"]')
    for msg in messages:
        geom = msg.find('geometry')
        old_y = float('inf')
        if geom is not None and geom.text:
            parts = [p.strip() for p in geom.text.split(',')]
            if len(parts) >= 2:
                try:
                    old_y = int(parts[1])
                except ValueError:
                    pass
        
        first_end = msg.find('linkFirstEndID')
        if first_end is not None:
            ref = get_attribute_with_ns("idref", first_end)
            if ref and old_y != float('inf'):
                fragment_target_y[ref] = old_y
        
        second_end = msg.find('linkSecondEndID')
        if second_end is not None:
            ref = get_attribute_with_ns("idref", second_end)
            if ref and old_y != float('inf'):
                fragment_target_y[ref] = old_y

    def get_original_y(elem):
        # If a message points to this fragment, use the message's original Y to enforce correct sorting
        xmi_id = get_attribute_with_ns("id", elem)
        if xmi_id in fragment_target_y:
            return fragment_target_y[xmi_id]

        geom = elem.find('geometry')
        if geom is not None and geom.text:
            parts = [p.strip() for p in geom.text.split(',')]
            if len(parts) >= 2:
                try:
                    return int(parts[1])
                except ValueError:
                    pass
        return float('inf')

    def process_views(views_node):
        nonlocal current_y
        if views_node is None:
            return

        elements = views_node.findall('mdElement')
        elements.sort(key=get_original_y)

        for md_elem in elements:
            cls_ = md_elem.get('elementClass')

            if cls_ == 'InteractionUse':
                geom = md_elem.find('geometry')
                if geom is None:
                    geom = create_sub_element(md_elem, 'geometry')
                
                geom.text = f"{MSG_X}, {current_y}, {MSG_WIDTH}, {MSG_HEIGHT}"
                
                xmi_id = get_attribute_with_ns("id", md_elem)
                if xmi_id:
                    fragment_mid_y[xmi_id] = current_y + (MSG_HEIGHT / 2)
                
                current_y += MSG_HEIGHT + GAP
            
            elif cls_ == 'StateInvariant':
                geom = md_elem.find('geometry')
                if geom is None:
                    geom = create_sub_element(md_elem, 'geometry')
                
                geom.text = f"{MSG_X}, {current_y}, 0, 0"
                current_y += MSG_HEIGHT + GAP

            elif cls_ == 'CombinedFragment':
                current_y += GAP
                frag_start_y = current_y
                current_y += 20

                operands_node = md_elem.find('operands')
                if operands_node is not None:
                    operands = operands_node.findall('mdElement[@elementClass="InteractionOperand"]')
                    operands.sort(key=get_original_y)
                    
                    for operand in operands:
                        op_start_y = current_y
                        current_y += 40

                        op_views = operand.find('mdOwnedViews')
                        if op_views is not None:
                            process_views(op_views)
                        
                        op_geom = operand.find('geometry')
                        if op_geom is None:
                            op_geom = create_sub_element(operand, 'geometry')
                        
                        op_height = current_y - op_start_y
                        op_geom.text = f"{FRAG_X}, {op_start_y}, {FRAG_WIDTH}, {op_height}"

                geom = md_elem.find('geometry')
                if geom is None:
                    geom = create_sub_element(md_elem, 'geometry')
                
                frag_height = current_y - frag_start_y
                geom.text = f"{FRAG_X}, {frag_start_y}, {FRAG_WIDTH}, {frag_height}"
                
                xmi_id = get_attribute_with_ns("id", md_elem)
                if xmi_id:
                    fragment_mid_y[xmi_id] = frag_start_y + (frag_height / 2)
                
                current_y += GAP

            else:
                nested_views = md_elem.find('mdOwnedViews')
                if nested_views is not None:
                    process_views(nested_views)

    main_views = root.find('.//mdOwnedViews')
    if main_views is not None:
        process_views(main_views)

    lifelines = root.findall('.//mdElement[@elementClass="SequenceLifeline"]')
    for i, ll in enumerate(lifelines):
        x = LIFELINE_START_X + (i * LIFELINE_SPACING)
        
        geom = ll.find('geometry')
        if geom is None:
            geom = create_sub_element(ll, 'geometry')
        geom.text = f"{x}, 75, 103, 21"

        line = ll.find('.//mdElement[@elementClass="LifeLineLine"]')
        if line is not None:
            line_geom = line.find('geometry')
            if line_geom is None:
                line_geom = create_sub_element(line, 'geometry')
            line_height = current_y - 96 + 50
            line_geom.text = f"{x + 51}, 96, 0, {line_height}"

    frame = root.find('.//mdElement[@elementClass="DiagramFrame"]')
    if frame is not None:
        geom = frame.find('geometry')
        if geom is None:
            geom = create_sub_element(frame, 'geometry')
        geom.text = f"5, 5, 700, {current_y + 100}"

    msg_data = []
    
    for msg in messages:
        geom = msg.find('geometry')
        old_y = float('inf')
        if geom is not None and geom.text:
            parts = [p.strip() for p in geom.text.split(',')]
            if len(parts) >= 2:
                try:
                    old_y = int(parts[1])
                except ValueError:
                    pass
        msg_data.append({'elem': msg, 'old_y': old_y, 'geom': geom})

    msg_data.sort(key=lambda item: item['old_y'], reverse=False)

    cumulative_shift = 0
    last_final_y = 0
    
    for item in msg_data:
        msg = item['elem']
        old_y = item['old_y']
        
        if old_y == float('inf'):
            old_y = 0
            
        target_mid_y = None
        
        first_end = msg.find('linkFirstEndID')
        if first_end is not None:
            ref = get_attribute_with_ns("idref", first_end)
            if ref in fragment_mid_y:
                target_mid_y = fragment_mid_y[ref]
                
        if target_mid_y is None:
            second_end = msg.find('linkSecondEndID')
            if second_end is not None:
                ref = get_attribute_with_ns("idref", second_end)
                if ref in fragment_mid_y:
                    target_mid_y = fragment_mid_y[ref]
                    
        if target_mid_y is not None:
            final_y = int(target_mid_y)
            cumulative_shift = final_y - old_y
        else:
            final_y = old_y + cumulative_shift

        # Prevent messages from overlapping visually if they are shifted too closely
        if final_y <= last_final_y:
            final_y = last_final_y + GAP
            cumulative_shift = final_y - old_y
            
        last_final_y = final_y

        geom = item['geom']
        if geom is None:
            geom = create_sub_element(msg, 'geometry')
            geom.text = f"0, {int(final_y)}, 0, {int(final_y)}"
        elif geom.text:
            parts = [p.strip() for p in geom.text.split(',')]
            for j in range(1, len(parts), 2):
                parts[j] = str(int(final_y))
            geom.text = ", ".join(parts)