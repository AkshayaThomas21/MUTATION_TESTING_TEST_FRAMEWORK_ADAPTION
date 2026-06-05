from tree_sitter import Language, Parser
import tree_sitter_c
import json
from core.file_operations import read_file


C_LANGUAGE = Language(tree_sitter_c.language())
parser = Parser(C_LANGUAGE)

def _extract_functions(node, code, functions):
    if node.type == 'function_definition':
        function_name = ""

        for child in node.children:
            if child.type == 'function_declarator':
                for grandchild in child.children:
                    if grandchild.type == 'identifier':
                        function_name = code[grandchild.start_byte:grandchild.end_byte]
                    if grandchild.type == 'parameter_list':
                        function_name += " " + code[grandchild.start_byte:grandchild.end_byte]
                        break

        if not function_name.strip():
            full_code = code[node.start_byte:node.end_byte]
            upto_paren = full_code.split(')', 1)[0]
            fallback_name = upto_paren + ')'
            function_name = fallback_name.strip()

        functions.append({
            "function_name": function_name,
            "code": code[node.start_byte:node.end_byte]
        })
        return

    for child in node.children:
        _extract_functions(child, code, functions)

def extract_functions(c_file_path, output_json_path="links.json"):
    functions = []

    cpp_code = read_file(c_file_path)
    tree = parser.parse(bytes(cpp_code, "utf8"))
    _extract_functions(tree.root_node, cpp_code, functions)

    data = {
        "file_path": c_file_path,
        "functions": functions
    }
    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    return functions
