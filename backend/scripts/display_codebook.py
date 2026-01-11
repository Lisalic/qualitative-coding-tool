import json

def parse_codebook_to_json(raw_text):
    codebook_structure = []
    
    current_family = None
    current_code = None
    
    lines = raw_text.strip().split('\n')
    
    for line in lines:
        line = line.strip()
        
        if line.startswith("### Code Family:"):
            family_name = line.replace("### Code Family:", "").strip()
            
            current_family = {
                "family_name": family_name,
                "codes": []
            }
            codebook_structure.append(current_family)
            
        elif line.startswith("#### Code Name:"):
            code_name = line.replace("#### Code Name:", "").strip()
            
            current_code = {
                "code_name": code_name,
                "definition": "" 
            }
            
            if current_family is not None:
                current_family["codes"].append(current_code)

        elif line.startswith("**Definition:**"):
            definition_text = line.replace("**Definition:**", "").strip()
            
            if current_code is not None:
                current_code["definition"] = definition_text

    return json.dumps(codebook_structure, indent=2)

