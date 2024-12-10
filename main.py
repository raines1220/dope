#!/usr/bin/env python3
import os
import sys
import shutil
import json
import argparse
import logging
import subprocess
import shlex

class OperationError(Exception):
    """Custom exception for operation errors."""
    pass

class PlanExecutor:
    def __init__(self, desktop_dir, plan_file, rollback_file=".rollbackinfo.json"):
        self.desktop_dir = os.path.abspath(desktop_dir)
        self.plan_file = plan_file
        self.rollback_file = os.path.join(self.desktop_dir, rollback_file)
        self.rollback_commands = []

        # Check desktop directory
        if not os.path.isdir(self.desktop_dir):
            raise OperationError(f"Desktop directory does not exist: {self.desktop_dir}")
        if not os.access(self.desktop_dir, os.W_OK):
            raise OperationError(f"No write permission on desktop directory: {self.desktop_dir}")

    def _is_within_desktop(self, path):
        abs_path = os.path.abspath(path)
        return abs_path.startswith(self.desktop_dir + os.sep)

    def _mkdir(self, rel_path):
        target_dir = os.path.join(self.desktop_dir, rel_path)
        if not self._is_within_desktop(target_dir):
            raise OperationError("Attempt to create directory outside of desktop.")
        if not os.path.exists(target_dir):
            # logging.info(f"Creating directory: {target_dir}")
            os.makedirs(target_dir, exist_ok=True)
            # Rollback: remove this directory
            self.rollback_commands.append(("RMDIR", rel_path))
        else:
            logging.info(f"Directory already exists: {target_dir}, skipping.")

    def _move(self, src_rel, dst_rel):
        src = os.path.join(self.desktop_dir, src_rel)
        dst = os.path.join(self.desktop_dir, dst_rel)
        if not (self._is_within_desktop(src) and self._is_within_desktop(dst)):
            raise OperationError("Attempt to move outside desktop.")
        if not os.path.exists(src):
            raise OperationError(f"Source file/folder does not exist for MOVE: {src}")

        if os.path.isdir(dst):
            new_path = os.path.join(dst, os.path.basename(src))
        else:
            new_path = dst

        # logging.info(f"Moving from {src} to {new_path}")
        old_path = src
        shutil.move(src, new_path)
        relative_new_path = os.path.relpath(new_path, self.desktop_dir)
        relative_old_path = os.path.relpath(old_path, self.desktop_dir)
        self.rollback_commands.append(("MOVE", relative_new_path, relative_old_path))

    def _rename(self, old_rel, new_rel):
        old_path = os.path.join(self.desktop_dir, old_rel)
        new_path = os.path.join(self.desktop_dir, new_rel)
        if not (self._is_within_desktop(old_path) and self._is_within_desktop(new_path)):
            raise OperationError("Attempt to rename outside desktop.")
        if not os.path.exists(old_path):
            raise OperationError(f"Old name does not exist for RENAME: {old_path}")

        # logging.info(f"Renaming {old_path} to {new_path}")
        os.rename(old_path, new_path)
        self.rollback_commands.append(("RENAME", new_rel, old_rel))

    def execute_plan(self):
        if not os.path.isfile(self.plan_file):
            raise OperationError(f"Plan file does not exist: {self.plan_file}")

        logging.info(f"Executing plan: {self.plan_file}")
        with open(self.plan_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                try:
                    parts = shlex.split(line)
                except ValueError as e:
                    raise OperationError(f"Error parsing line: {line}. {e}")

                if not parts:
                    continue

                cmd = parts[0].upper()
                try:
                    if cmd == "MKDIR":
                        if len(parts) != 2:
                            raise OperationError("Invalid MKDIR syntax. Usage: MKDIR \"<dir>\"")
                        self._mkdir(parts[1])

                    elif cmd == "MOVE":
                        if len(parts) != 3:
                            raise OperationError("Invalid MOVE syntax. Usage: MOVE \"<src>\" \"<dst>\"")
                        self._move(parts[1], parts[2])

                    elif cmd == "RENAME":
                        if len(parts) != 3:
                            raise OperationError("Invalid RENAME syntax. Usage: RENAME \"<old>\" \"<new>\"")
                        self._rename(parts[1], parts[2])

                    else:
                        raise OperationError(f"Unknown command: {cmd}")
                except OperationError as e:
                    logging.error(f"Error encountered: {e}")
                    continue
                except Exception as e:
                    logging.exception(f"Unexpected error: {e}")
                    continue

    def save_rollback_info(self):
        with open(self.rollback_file, 'w', encoding='utf-8') as f:
            json.dump(self.rollback_commands, f)
        logging.info(f"Rollback information saved to {self.rollback_file}")

    def load_rollback_info(self):
        if not os.path.isfile(self.rollback_file):
            raise OperationError("No rollback information file found.")
        with open(self.rollback_file, 'r', encoding='utf-8') as f:
            self.rollback_commands = json.load(f)

    def rollback(self):
        logging.info("Starting rollback...")
        for cmd_tuple in reversed(self.rollback_commands):
            cmd = cmd_tuple[0]
            if cmd == "RMDIR":
                dir_rel = cmd_tuple[1]
                dir_path = os.path.join(self.desktop_dir, dir_rel)
                if os.path.isdir(dir_path):
                    if len(os.listdir(dir_path)) == 0:
                        logging.info(f"Removing directory: {dir_path}")
                        os.rmdir(dir_path)
                    else:
                        logging.warning(f"Directory not empty during rollback: {dir_path}, skipping removal.")
            elif cmd == "MOVE":
                src_rel = cmd_tuple[1]
                dst_rel = cmd_tuple[2]
                src_path = os.path.join(self.desktop_dir, src_rel)
                dst_path = os.path.join(self.desktop_dir, dst_rel)
                if os.path.exists(src_path) and self._is_within_desktop(dst_path):
                    logging.info(f"Rollback MOVE: {src_path} -> {dst_path}")
                    shutil.move(src_path, dst_path)
            elif cmd == "RENAME":
                old_rel = cmd_tuple[1]
                new_rel = cmd_tuple[2]
                old_path = os.path.join(self.desktop_dir, old_rel)
                new_path = os.path.join(self.desktop_dir, new_rel)
                if os.path.exists(old_path):
                    logging.info(f"Rollback RENAME: {old_path} -> {new_path}")
                    os.rename(old_path, new_path)
        logging.info("Rollback completed.")

        self.rollback_commands.clear()
        if os.path.exists(self.rollback_file):
            os.remove(self.rollback_file)
            logging.info(f"Removed rollback info file: {self.rollback_file}")

    def plan_mode(self):
        try:
            # Adjust the find command to print .app directories but not their internal contents.
            find_command = [
                "find", self.desktop_dir,
                "(",
                    "-type", "d", "-name", "*.app", "-print", "-prune",
                ")", "-o", "-print"
            ]

            result = subprocess.check_output(find_command, universal_newlines=True)
        except subprocess.CalledProcessError as e:
            raise OperationError(f"Find command failed: {e}")

        all_paths = result.strip().split("\n")
        # Exclude the desktop directory itself from the list
        all_paths = [p for p in all_paths if p != self.desktop_dir]

        listing_info = []
        for path in all_paths:
            rel_path = os.path.relpath(path, self.desktop_dir)
            if os.path.isdir(path):
                listing_info.append(f"[DIR] {rel_path}")
            else:
                file_info = f"[FILE] {rel_path}"
                listing_info.append(file_info)

        listing_str = "\n".join(listing_info)
        prompt = f"""
    Below is a list of all files and directories in the {self.desktop_dir} directory.
    For each file, only the file name and path are included.

    Please create a `.plan` file containing instructions to reorganize this directory based on this information.
    Your goal is to minimize the time needed for a human to find a file/directories.
    This means the level of nesting should not be larger than 2
    Also, the way you create directories should contain the most information possible, while still being easy to read and contain as most files as possible.
    The number of top-level categories should be close to the number of nested categories in each top-level category.
    The number of leaf directories should be close to the number of files in each leaf directory.
    Don't use wildcards in your plan, each line representing changing a single file or directory.
    You can use the following commands:
    - MKDIR "<dir>"
    - MOVE "<src>" "<dst>"
    - RENAME "<old>" "<new>"

    The goal is to make the desktop structure more organized.

    Here is the list of files and directories:
    {listing_str}

    After completing, please output the contents of your `.plan` file below.
    """

        prompt_file = f"{self.plan_file}.prompt"
        with open(prompt_file, 'w', encoding='utf-8') as f:
            f.write(prompt)
        print(f"Prompt saved to {prompt_file}. Please upload this file to ChatGPT for further instructions.")

def main():
    parser = argparse.ArgumentParser(description="Manage Desktop according to a plan file.")
    parser.add_argument("--desktop", required=True, help="Path to the desktop directory.")
    parser.add_argument("--plan-file", required=True, help="Path to the .plan file.")
    parser.add_argument("--mode", choices=["plan", "execute",], required=True, help="Mode to run: plan/execute/rollback")

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    executor = PlanExecutor(args.desktop, args.plan_file)

    if args.mode == "plan":
        # Generate prompt and get user's .plan input
        try:
            executor.plan_mode()
        except OperationError as e:
            logging.error(f"Error in plan mode: {e}")
            sys.exit(1)
        except Exception as e:
            logging.exception(f"Unexpected error in plan mode: {e}")
            sys.exit(1)

    elif args.mode == "execute":
        try:
            executor.execute_plan()
            executor.save_rollback_info()
            confirm = input("Plan executed. Confirm changes? (y/n): ").strip().lower()
            if confirm == 'y':
                # User confirmed changes, remove rollback file
                if os.path.exists(executor.rollback_file):
                    os.remove(executor.rollback_file)
                    logging.info("Changes confirmed. Rollback information removed.")
                print("Changes have been confirmed.")
            else:
                # User did not confirm, perform rollback
                logging.info("User declined changes, performing rollback.")
                executor.load_rollback_info()
                executor.rollback()
                print("Changes rolled back.")

        except OperationError as e:
            logging.error(f"Error encountered: {e}")
            # Encountered error, perform rollback
            # if executor.rollback_commands:
            #     logging.info("Attempting to rollback due to error...")
            #     executor.rollback()
            # sys.exit(1)
        except Exception as e:
            logging.exception(f"Unexpected error: {e}")
            # if executor.rollback_commands:
            #     logging.info("Attempting to rollback due to unexpected error...")
            #     executor.rollback()
            # sys.exit(1)

if __name__ == "__main__":
    main()
