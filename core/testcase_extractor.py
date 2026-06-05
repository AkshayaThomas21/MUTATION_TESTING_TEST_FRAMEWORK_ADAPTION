import os
import re
import json

from core.file_operations import read_file


def remove_comments(text: str):
    text = re.sub(r"//.*?$", "", text, flags=re.MULTILINE)
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    return text


def find_all_test_blocks_generic(file_content: str):
    blocks = []
    pattern = re.compile(r'([A-Za-z0-9_]+\s*\([^)]*\)\s*\{)', re.MULTILINE)

    for match in pattern.finditer(file_content):
        start = match.start()
        open_brace_pos = file_content.find("{", start)
        if open_brace_pos == -1:
            continue

        brace_count = 1
        pos = open_brace_pos + 1

        while pos < len(file_content):
            if file_content[pos] == "{":
                brace_count += 1
            elif file_content[pos] == "}":
                brace_count -= 1
                if brace_count == 0:
                    block = file_content[start:pos + 1]
                    blocks.append(block.strip())
                    break
            pos += 1

    return blocks


def gtest_extract_blocks_for_function(test_cpp_path: str, func_name: str):
    if not os.path.exists(test_cpp_path):
        return ""

    content = read_file(test_cpp_path)
    blocks = find_all_test_blocks_generic(content)
    clean_name = func_name.split("(")[0].strip()

    call_pattern = re.compile(r'\b' + re.escape(clean_name) + r'\s*\(')

    results = []
    for block in blocks:
        block_no_comments = remove_comments(block)
        if call_pattern.search(block_no_comments):
            results.append(block)

    return ",\n".join(results) if results else ""


def extract_testcases(c_file_path, test_case_folder_path, output_json_path="tests.json"):
    """Extract GTest testcases."""
    if not os.path.exists("links.json"):
        print("[ERROR] links.json not found")
        return {}

    with open("links.json", "r", encoding="utf-8") as f:
        links_data = json.load(f)

    functions = links_data.get("functions", [])
    file_path = links_data.get("file_path", "")

    if not functions:
        print("[WARNING] No functions in links.json")
        return {}

    functions_data = []

    # Pick the .cpp file inside test_case_folder
    test_cpp_path = None
    for f in os.listdir(test_case_folder_path):
        if f.lower().endswith(".cpp"):
            test_cpp_path = os.path.join(test_case_folder_path, f)
            break

    if not test_cpp_path:
        print("[ERROR] No .cpp test file found inside test_case_folder (GTest)")
        return {}

    for func in functions:
        func_name = func["function_name"]
        test_blocks = gtest_extract_blocks_for_function(test_cpp_path, func_name)

        functions_data.append({
            "function_name": func_name,
            "code": func.get("code", ""),
            "testcases": test_blocks
        })

    result = {
        os.path.basename(file_path): [
            {
                "file_path": file_path,
                "functions": functions_data
            }
        ]
    }

    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print(f"[INFO] Testcases saved to {output_json_path}")
    return result
