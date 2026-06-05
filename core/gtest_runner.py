import os
import re
import shutil
import subprocess
import json
import logging
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import xml.etree.ElementTree as ET

log = logging.getLogger(__name__)


def ensure_empty_dir(path):
    if os.path.exists(path):
        for item in os.listdir(path):
            item_path = os.path.join(path, item)
            try:
                if os.path.isfile(item_path) or os.path.islink(item_path):
                    os.unlink(item_path)
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path)
            except Exception as e:
                print(f"[WARNING] Failed to delete {item_path}: {e}")
    else:
        os.makedirs(path, exist_ok=True)


class GTestMutationRunner:
    def __init__(self, project_path: str, script_path: str, test_target: str):
        self.project_path = project_path
        self.script_path = script_path
        self.test_target = test_target

    def _find_xml_report(self, search_path: str, target_filename: str) -> str | None:
        expected_xml_file = f"{target_filename}.xml"
        for root, dirs, files in os.walk(search_path):
            for file in files:
                if file == expected_xml_file:
                    return os.path.join(root, file)
        return None

    def build_original_project(self):
        env = os.environ.copy()
        if self.test_target:
            env["TEST_TARGET"] = self.test_target
        return subprocess.run(
            ['cmd.exe', '/c', self.script_path],
            cwd=self.project_path,
            env=env,
            check=False
        )

    def delete_existing_clones(self, clones_root="clones"):
        if os.path.exists(clones_root):
            shutil.rmtree(clones_root)
            print("Deleted existing clones folder")

    def inject_mutant_code(self, c_file_path, original_code, mutated_code):
        if not os.path.exists(c_file_path):
            print(f"File not found for mutation injection: {c_file_path}")
            return False

        with open(c_file_path, "r", encoding="utf-8") as f:
            content = f.read()

        content = content.replace("\r\n", "\n").replace("\r", "\n")
        original_code = original_code.replace("\r\n", "\n").replace("\r", "\n").strip("\n")
        mutated_code = mutated_code.replace("\r\n", "\n").replace("\r", "\n").strip("\n")

        def collapse_macros(lines):
            merged = []
            buffer = ""
            for line in lines:
                if buffer:
                    buffer += line
                else:
                    buffer = line
                if buffer.rstrip().endswith("\\"):
                    buffer = buffer.rstrip() + "\n"
                    continue
                merged.append(buffer)
                buffer = ""
            if buffer:
                merged.append(buffer)
            return merged

        content_lines = collapse_macros(content.split("\n"))
        original_lines = collapse_macros(original_code.split("\n"))
        mutated_lines = collapse_macros(mutated_code.split("\n"))

        def strip_comments(s):
            return re.sub(r"//.*|/\*.*?\*/", "", s)

        def normalize(s):
            s = strip_comments(s)
            s = s.strip()
            s = re.sub(r"\s+", " ", s)
            s = re.sub(r"[;,\s]+$", "", s)
            return s

        replaced = False

        for i in range(len(content_lines) - len(original_lines) + 1):
            window = content_lines[i:i+len(original_lines)]
            if [normalize(x) for x in window] == [normalize(x) for x in original_lines]:
                content_lines[i:i+len(original_lines)] = mutated_lines
                replaced = True
                break

        if not replaced:
            from difflib import SequenceMatcher
            for i in range(len(content_lines) - len(original_lines) + 1):
                window = content_lines[i:i+len(original_lines)]
                seq = SequenceMatcher(
                    None,
                    [normalize(x) for x in window],
                    [normalize(x) for x in original_lines]
                )
                if seq.ratio() > 0.85:
                    content_lines[i:i+len(original_lines)] = mutated_lines
                    replaced = True
                    break
                
        # Third attempt: skip truly blank lines + fuzzy match (handles extra blank lines)
        if not replaced:
            content_nonempty = [(i, line) for i, line in enumerate(content_lines) if line.strip()]
            original_nonempty = [line for line in original_lines if line.strip()]

            if original_nonempty and len(content_nonempty) >= len(original_nonempty):
                norm_original = [normalize(x) for x in original_nonempty]
                best_ratio = 0
                best_start = -1

                for start in range(len(content_nonempty) - len(original_nonempty) + 1):
                    window = content_nonempty[start:start + len(original_nonempty)]
                    norm_window = [normalize(x[1]) for x in window]
                    ratio = SequenceMatcher(None, norm_window, norm_original).ratio()
                    if ratio > best_ratio:
                        best_ratio = ratio
                        best_start = start

                if best_ratio >= 0.7 and best_start >= 0:
                    window = content_nonempty[best_start:best_start + len(original_nonempty)]
                    first_idx = window[0][0]
                    last_idx = window[-1][0]
                    content_lines[first_idx:last_idx + 1] = mutated_lines
                    replaced = True

        if not replaced:
            print("Original code not found in file. Skipped mutation.")
            return False

        final_content = "\r\n".join(content_lines)
        with open(c_file_path, "w", encoding="utf-8") as f:
            f.write(final_content)

        print(f"Injected mutation in: {c_file_path}")
        return True

    def create_clones_from_mutants(self, mutant_json_path: str, selected_c_file: str, clones_root="clones"):
        STATIC_IGNORE = {
            "build", ".metadata", ".bin", "workspace", "plugins",
            "CodesysTestProject", "Documentation", ".doctrees",
            "_sources", "packages", ".git",
        }

        def smart_ignore(base_dir):
            def _ignore(dirpath, names):
                ignored = []
                for name in names:
                    full_path = os.path.join(dirpath, name)
                    if name in STATIC_IGNORE:
                        ignored.append(name)
                        continue
                    try:
                        if len(os.path.abspath(full_path)) > 230:
                            ignored.append(name)
                    except Exception:
                        ignored.append(name)
                return ignored
            return _ignore

        with open(mutant_json_path, "r") as f:
            mutant_data = json.load(f)

        c_file_name = os.path.basename(selected_c_file)
        updated_function_map = {}

        for comp_idx, (func_name, mutants) in enumerate(mutant_data.items(), start=1):
            component_dir = os.path.join(clones_root, f"c{comp_idx}")
            os.makedirs(component_dir, exist_ok=True)

            updated_mutants = []

            for copy_idx, mutant in enumerate(mutants, start=1):
                clone_path = os.path.join(component_dir, f"copy-{copy_idx}")

                try:
                    shutil.copytree(
                        src=self.project_path,
                        dst=clone_path,
                        dirs_exist_ok=True,
                        ignore=smart_ignore(self.project_path),
                    )
                except shutil.Error as e:
                    errors = e.args[0]
                    print(f"[WARNING] {len(errors)} files skipped during cloning")

                print(f"Created {clone_path} for {func_name} mutant-{copy_idx}")

                original_code = mutant.get("original_code")
                mutated_code = mutant.get("mutated_code")

                c_file_path = None
                for root, dirs, files in os.walk(clone_path):
                    for file in files:
                        if file == c_file_name:
                            c_file_path = os.path.join(root, file)
                            break
                    if c_file_path:
                        break

                if not c_file_path:
                    print(f"[WARNING] {c_file_name} not found in {clone_path}. Skipping mutation.")
                    continue

                success = self.inject_mutant_code(c_file_path, original_code, mutated_code)
                if success:
                    updated_mutants.append(mutant)

            if updated_mutants:
                updated_function_map[func_name] = updated_mutants

        with open(mutant_json_path, "w", encoding="utf-8") as f:
            json.dump(updated_function_map, f, indent=4)

        print("Updated mutant JSON file.")

    def run_tests_on_clones(self, selected_c_file: str, clones_root="clones", logs_root="logs"):
        if os.path.exists(logs_root):
            shutil.rmtree(logs_root)
        os.makedirs(logs_root, exist_ok=True)

        print("[INFO] Running GTEST clones in PARALLEL...")

        def _run_cmd_and_log(work_dir, log_path):
            try:
                print(f"Running tests in {work_dir}")
                env = os.environ.copy()
                if self.test_target:
                    env["TEST_TARGET"] = self.test_target

                with open(log_path, "w", encoding="utf-8") as lf:
                    subprocess.run(
                        ['cmd.exe', '/c', self.script_path],
                        cwd=work_dir,
                        env=env,
                        stdout=lf,
                        stderr=subprocess.STDOUT,
                        check=False
                    )
            except Exception as e:
                with open(log_path, "a", encoding="utf-8") as lf:
                    lf.write(f"\nERROR: {e}\n")

        tasks = []
        with ThreadPoolExecutor(max_workers=4) as executor:
            for comp_folder in sorted(os.listdir(clones_root)):
                comp_path = os.path.join(clones_root, comp_folder)
                if not os.path.isdir(comp_path):
                    continue

                for clone_folder in sorted(os.listdir(comp_path)):
                    clone_path = os.path.join(comp_path, clone_folder)
                    if os.path.isdir(clone_path):
                        log_comp_path = os.path.join(logs_root, comp_folder)
                        os.makedirs(log_comp_path, exist_ok=True)

                        log_index = clone_folder.replace("copy-", "logs-")
                        log_file = os.path.join(log_comp_path, f"{log_index}.txt")

                        tasks.append(
                            executor.submit(_run_cmd_and_log, clone_path, log_file)
                        )

            for _ in as_completed(tasks):
                pass

        print("[INFO] Finished GTest parallel execution.")

    def delete_existing_logs(self, logs_root="logs"):
        if os.path.exists(logs_root):
            shutil.rmtree(logs_root)
            print("Deleted existing logs folder")

    def delete_existing_temp(self, temp_root="temp"):
        if os.path.exists(temp_root):
            shutil.rmtree(temp_root)
            print("Deleted existing temp folder")

    def classify_and_generate_temp_reports(self, mutant_json_path, tests_json_path,
                                           selected_c_file, logs_root="logs",
                                           temp_root="temp", clones_root="clones"):
        with open(mutant_json_path, "r", encoding="utf-8") as f:
            mutant_data = json.load(f)

        with open(tests_json_path, "r", encoding="utf-8") as f:
            tests_data = json.load(f)

        c_file_name = os.path.basename(selected_c_file)

        if os.path.exists(temp_root):
            shutil.rmtree(temp_root)
        os.makedirs(temp_root, exist_ok=True)

        for comp_folder in os.listdir(logs_root):
            comp_path = os.path.join(logs_root, comp_folder)
            if not os.path.isdir(comp_path):
                continue

            func_index = int(comp_folder.replace("c", "")) - 1
            func_name = list(mutant_data.keys())[func_index]
            mutants = mutant_data[func_name]

            testcases = "N/A"
            for entry in tests_data.get(c_file_name, []):
                for fn in entry.get("functions", []):
                    if fn.get("function_name") == func_name:
                        testcases = fn.get("testcases", "N/A")
                        break
                if testcases != "N/A":
                    break

            total = len(mutants)
            survived = 0
            killed = 0
            build_error = 0

            mutant_reports = []

            for idx, mutant in enumerate(mutants, start=1):
                log_file = f"logs-{idx}.txt"
                log_path = os.path.join(comp_path, log_file)
                status = "Unknown"
                log_excerpt = ""

                try:
                    with open(log_path, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                    content = "".join(lines)
                    last_line = lines[-1].strip() if lines else ""

                    clone_folder_path = os.path.join(clones_root, comp_folder, f"copy-{idx}")
                    xml_report_path = self._find_xml_report(clone_folder_path, func_name)

                    if xml_report_path:
                        try:
                            tree = ET.parse(xml_report_path)
                            root_elem = tree.getroot()
                            if root_elem.get('success') == 'ok':
                                status = "Survived"
                                survived += 1
                            else:
                                status = "Killed"
                                killed += 1
                        except ET.ParseError:
                            status = "Build-error"
                            build_error += 1
                    else:
                        test_summary_re = re.compile(
                            r"Test:\s*(\d+)\s*succeeded,\s*(\d+)\s*failed,\s*(\d+)\s*skipped",
                            re.IGNORECASE
                        )
                        summary_match = None
                        for line in lines:
                            m = test_summary_re.search(line)
                            if m:
                                summary_match = m
                                break

                        survived_by_summary = False
                        killed_by_summary = False

                        if summary_match:
                            succeeded_cnt = int(summary_match.group(1))
                            failed_cnt = int(summary_match.group(2))
                            if succeeded_cnt > 0 and failed_cnt == 0:
                                survived_by_summary = True
                            if failed_cnt > 0:
                                killed_by_summary = True

                        if ("PASS" in last_line) or survived_by_summary:
                            status = "Survived"
                            survived += 1
                        elif ("FAIL" in last_line) or killed_by_summary:
                            status = "Killed"
                            killed += 1
                            start_idx, end_idx = None, None
                            for j, line in enumerate(lines):
                                if "[INFO] Building full project..." in line:
                                    start_idx = j
                                if "failed" in line.lower():
                                    end_idx = j
                                    break
                            if start_idx is not None and end_idx is not None:
                                log_excerpt = "".join(lines[start_idx:end_idx+1]).strip()
                        elif "Error" in last_line or "ERROR" in last_line:
                            status = "Build-error"
                            build_error += 1
                        else:
                            status = "Unknown"

                except Exception as e:
                    status = "Log Missing/Error"
                    print(f"An error occurred while classifying mutant {idx}: {e}")

                mutant_reports.append({
                    "id": mutant.get("mutant_id", "N/A"),
                    "original_code": mutant.get("original_code", "N/A"),
                    "mutated_code": mutant.get("mutated_code", "N/A"),
                    "status": status,
                    "log": log_excerpt,
                    "mutant_category": mutant.get("mutant_category", "Uncategorized")
                })

            mutation_score = (killed / (killed + survived)) * 100 if (killed + survived) else 0

            json_report = {
                "c_file": c_file_name,
                "function_name": func_name,
                "testcases": testcases if isinstance(testcases, list) else [testcases],
                "total_mutants": total,
                "survived": survived,
                "killed": killed,
                "build_error": build_error,
                "mutation_score": round(mutation_score, 2),
                "mutants": mutant_reports
            }

            report_path = os.path.join(temp_root, f"{comp_folder}.json")
            with open(report_path, "w", encoding="utf-8") as f:
                json.dump(json_report, f, indent=2)

            print(f"JSON report saved: {report_path}")

        self.generate_mutation_report_from_json(
            json_dir=temp_root,
            output_path=os.path.join(temp_root, "mutation_report.html")
        )

    def generate_mutation_report_from_json(self, json_dir="temp", output_path="output.html"):
        report_time = datetime.now().strftime("%d/%m/%Y, %I:%M:%S %p")
        all_files = sorted(f for f in os.listdir(json_dir) if f.endswith(".json"))

        if not all_files:
            print("No JSON files found in temp directory.")
            return

        sample_data = json.load(open(os.path.join(json_dir, all_files[0]), "r", encoding="utf-8"))
        c_file_name = sample_data.get("c_file", "Unknown.c")

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Mutation Test Report</title>
<style>
    body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f9f9f9; }}
    h1 {{ color: #333; }}
    .function-block {{ background-color: #fff; border: 1px solid #ddd; border-left: 5px solid #4CAF50; padding: 20px; margin-bottom: 20px; }}
    .function-name {{ font-size: 1.2em; color: #333; }}
    table {{ width: 100%; border-collapse: collapse; margin: 10px 0; }}
    th, td {{ border: 1px solid #999; padding: 8px; text-align: left; vertical-align: top; }}
    th {{ background-color: royalblue; color: white; }}
    .code-block {{ background-color: #f4f4f4; padding: 10px; border-radius: 5px; font-family: monospace; white-space: pre-wrap; }}
    .log-block {{ background-color: #222; color: #eee; padding: 10px; border-radius: 5px; font-family: monospace; white-space: pre-wrap; max-height: 300px; overflow-y: auto; }}
</style>
</head>
<body>
<h1>Mutation Test Report</h1>
<h4>Generated on: {report_time}</h4>
<hr>
<h2>.c File: <code style="color: teal">{c_file_name}</code></h2>
"""

        for filename in all_files:
            with open(os.path.join(json_dir, filename), "r", encoding="utf-8") as f:
                data = json.load(f)

            func_name = data.get("function_name", "Unknown")
            testcases = data.get("testcases", [])
            mutants = data.get("mutants", [])
            total = data.get("total_mutants", 0)
            survived_cnt = data.get("survived", 0)
            killed_cnt = data.get("killed", 0)
            build_error_cnt = data.get("build_error", 0)
            mutation_score = data.get("mutation_score", 0.0)

            html += f"""
<div class="function-block">
    <div class="function-name">Function: <code>{func_name}</code></div>
    <div>Testcase(s): {", ".join(testcases) if testcases else "N/A"}</div>
    <hr>
"""

            for i, mutant in enumerate(mutants, start=1):
                color = "green" if mutant.get("status") == "Killed" else ("red" if mutant.get("status") == "Survived" else "orange")
                html += f"""
    <h3>Mutant #{i}</h3>
    <table><tr><th>Original Code</th><th>Mutated Code</th></tr>
    <tr><td><div class="code-block">{mutant.get("original_code", "")}</div></td>
        <td><div class="code-block">{mutant.get("mutated_code", "")}</div></td></tr></table>
    <p>Category: <strong>{mutant.get("mutant_category", "Uncategorized")}</strong></p>
    <p>Status: <strong style="color:{color}">{mutant.get("status", "Unknown")}</strong></p>
"""
                if mutant.get("status") == "Killed" and mutant.get("log"):
                    html += f'<div class="log-block">{mutant["log"]}</div>'

            html += f"""
    <h3>Summary</h3>
    <ul>
        <li>Total Mutants: {total}</li>
        <li>Survived: {survived_cnt}</li>
        <li>Killed: {killed_cnt}</li>
        <li>Build Errors: {build_error_cnt}</li>
        <li>Mutation Score: <strong>{mutation_score:.2f}%</strong></li>
    </ul>
</div>
"""

        html += "</body></html>"

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)

        print(f"HTML report generated at: {output_path}")

    def get_next_run_dir(self, base="ranked"):
        os.makedirs(base, exist_ok=True)
        existing = [d for d in os.listdir(base) if d.startswith("run")]
        if not existing:
            return os.path.join(base, "run1"), 1
        nums = [int(d.replace("run", "")) for d in existing if d.replace("run", "").isdigit()]
        next_num = max(nums) + 1
        next_dir = os.path.join(base, f"run{next_num}")
        os.makedirs(next_dir, exist_ok=True)
        return next_dir, next_num

    def rank_mutants(self, temp_folder="temp", base_ranked_dir="ranked",
                     run_idx=None, func_idx=1, func_name=None):
        from src.llm_runnable import create_runnable
        from src.prompts import rank_mutants_agent_prompt
        from src.data_classes import RankedMutantsOutput
        from src.agents import MutantRanker

        if run_idx is None:
            run_dir, run_idx = self.get_next_run_dir(base_ranked_dir)
        else:
            run_dir = os.path.join(base_ranked_dir, f"run{run_idx}")
            os.makedirs(run_dir, exist_ok=True)

        func_dir = os.path.join(run_dir, f"c{func_idx}")
        os.makedirs(func_dir, exist_ok=True)

        target_path = os.path.join(temp_folder, f"c{func_idx}.json")
        if not os.path.exists(target_path):
            print(f"[WARNING] Expected temp file not found: {target_path}")
            return func_dir, None

        with open(target_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            all_mutants = [
                {
                    "original_code": m.get("original_code"),
                    "mutated_code": m.get("mutated_code"),
                    "status": m.get("status"),
                    "mutant_category": m.get("mutant_category"),
                    "function_name": func_name,
                }
                for m in data.get("mutants", [])
            ]

        if not all_mutants:
            print("No mutants found to rank.")
            return func_dir, None

        print(f"[INFO] Ranking {len(all_mutants)} mutants locally...")
        runnable = (
            create_runnable(prompt=rank_mutants_agent_prompt)
            .get_runnable_with_structured_output(RankedMutantsOutput)
        )
        ranker = MutantRanker(runnable)
        result = ranker(all_mutants)

        ranked_output = {
            "function_name": func_name,
            "ranked_mutants": [m.dict() if hasattr(m, "dict") else m for m in result["ranked_mutants"]]
        }

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        ranked_file = os.path.join(func_dir, f"ranked_mutants_{timestamp}.json")

        with open(ranked_file, "w", encoding="utf-8") as f:
            json.dump(ranked_output, f, indent=4)

        print(f"[INFO] Ranked mutants saved to {ranked_file}")
        return func_dir, ranked_file

    def full_clone_pipeline(self, mutant_json_path: str, selected_c_file: str, rerun=False):
        self.build_original_project()
        self.delete_existing_clones()
        self.create_clones_from_mutants(mutant_json_path, selected_c_file)
        self.delete_existing_logs()
        self.run_tests_on_clones(selected_c_file)
        self.delete_existing_temp()

        self.classify_and_generate_temp_reports(
            mutant_json_path=mutant_json_path,
            tests_json_path="tests.json",
            selected_c_file=selected_c_file,
            logs_root="logs",
            temp_root="temp",
            clones_root="clones"
        )

        if rerun:
            feedback_path = os.path.join("intermediate", "user_feedback.txt")
            if os.path.exists(feedback_path):
                os.remove(feedback_path)
                print("User feedback consumed and removed after feedback run.")
        return
