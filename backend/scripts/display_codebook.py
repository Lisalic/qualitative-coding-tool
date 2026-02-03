import json

def parse_codebook_to_json(raw_text):
    codebook_structure = []

    current_family = None
    current_code = None
    content_buffer = []

    lines = raw_text.strip().split('\n')

    for line in lines:
        line = line.strip()

        if line.startswith("### Code Family:"):
            # Save any buffered content to the last code of the current family, or to the current family if no codes
            if current_code is not None and content_buffer:
                current_code["content"] = "\n".join(content_buffer).strip()
                content_buffer = []
            elif current_family is not None and content_buffer:
                current_family["content"] = "\n".join(content_buffer).strip()
                content_buffer = []

            family_name = line.replace("### Code Family:", "").strip()

            current_family = {
                "family_name": family_name,
                "content": "",
                "codes": []
            }
            codebook_structure.append(current_family)
            current_code = None  # Reset current code when starting new family

        elif line.startswith("#### Code Name:"):
            # Save any buffered content to the previous code, or to current family if no previous code
            if current_code is not None and content_buffer:
                current_code["content"] = "\n".join(content_buffer).strip()
                content_buffer = []
            elif current_family is not None and content_buffer:
                current_family["content"] = "\n".join(content_buffer).strip()
                content_buffer = []

            code_name = line.replace("#### Code Name:", "").strip()

            current_code = {
                "code_name": code_name,
                "content": ""
            }

            if current_family is not None:
                current_family["codes"].append(current_code)
        else:
            # Collect all content lines (including what would have been definitions)
            if line:  # Only add non-empty lines
                content_buffer.append(line)
    
    if current_code is not None and content_buffer:
        current_code["content"] = "\n".join(content_buffer).strip()
    elif current_family is not None and content_buffer:
        current_family["content"] = "\n".join(content_buffer).strip()

    return json.dumps(codebook_structure, indent=2)

