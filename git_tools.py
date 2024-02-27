import argparse
import logging
import subprocess
import sys
from typing import Optional, Sequence


class TermString:
    """
    Class for terminal colors

    This is to avoid adding 3rd party packages

    Args:
        string: String to print in the terminal
        *formatting: formats (colors, bold, etc) to apply

    """

    formats = {
        "GREEN": "\033[92m",
        "CYAN": "\033[96m",
        "BOLD": "\033[1m",
        "YELLOW": "\033[33m",
        "RED": "\033[31m",
        "END": "\033[0m",
    }

    def __init__(self, string: str, *formatting: tuple):
        self._string = str(string)
        self._formatting = formatting

    def __repr__(self) -> str:
        output = self._string
        for fmt in self._formatting:
            output = f"{self.formats[fmt]}{output}{self.formats['END']}"
        return output

    def __len__(self) -> int:
        return len(self._string)


def exe_cmd(cmd: list) -> str:
    """
    executes a command in the shell and returns the output
    """
    logging.debug(f"executing: {cmd}")
    return subprocess.run(cmd, capture_output=True, text=True, shell=True).stdout


def current_branch() -> str:
    """
    Returns the current branch
    """
    cmd = ["git rev-parse --abbrev-ref HEAD"]
    return exe_cmd(cmd).splitlines()[0]


def latest_commit_hash(branch: str) -> str:
    """
    Returns the latest commit hash for the given branch
    """
    cmd = [f"git log --oneline -n 1 --format='%H' {branch}"]
    return exe_cmd(cmd).splitlines()[0]


def latest_commit_title(branch: str) -> str:
    """
    Returns the latest commit title for the given branch
    """
    cmd = [f"git log --oneline -n 1 --format='%s' {branch}"]
    return exe_cmd(cmd).splitlines()[0]


def gather_upstreams() -> dict:
    """
    Finds upstream branch names for all local branches

    Returns:
        A dictionary of branch_name: upstream_branch
    """

    cmd = [
        "git for-each-ref --format='%(refname:short) %(upstream:short)' refs/heads",
    ]
    result = exe_cmd(cmd)

    # Dictionary of branch_name: upstream_branch
    branches = {}
    for line in result.splitlines():
        split = line.split(" ")
        branch = split[0]
        upstream = split[1]

        # Empty string is considered to have no upstream
        # "origin/" upstreams are also considered to have none (e.g. main/master)
        if upstream == "" or upstream.startswith("origin/"):
            upstream = None

        branches[branch] = upstream
    return branches


def commit_count_difference(branch_a: str, branch_b: str) -> Optional[int]:
    """
    Returns the number of commits difference between two branches

    Args:
        branc_a, branc_b: string branch names to compare

    Returns:
        int difference, or None
    """
    if branch_a is None or branch_b is None:
        return None

    cmd = [
        f"git rev-list {branch_a}..{branch_b} --count",
    ]
    result = exe_cmd(cmd).splitlines()

    if result:
        return int(result[0])
    else:
        return None


def checkout(branch: str) -> None:
    """
    Checks out the given branch
    """
    logging.debug(f"checkout {branch}")
    cmd = [f"git checkout {branch}"]
    exe_cmd(cmd)


def rebase(upstream: str, child: str) -> None:
    """
    Rebased child branch onto upstream branch
    """
    logging.debug(f"rebase {TermString(upstream, 'CYAN')} {TermString(child, 'GREEN')}")
    cmd = [f"git rebase {upstream} {child}"]
    return exe_cmd(cmd)


def upstream_tree() -> dict:
    """
    Constructs a simple tree based on each branches upstream branch.

    TODO: This is messy.  I'll fix it when it's worth the time.

    Returns:
        Dict in the form "branch_name": "node" where node contains:
            node.name - same as branch name in the dict
            node.children - nodes that consider this node an upstream parent
            node.ahead - number of commits on this branch
            node.behind - number of commits this branch is behind master
            node.title - latest commit title
            node.hash - latest commit hash
            node.active - is this the current branch? True/False
            node.root - is this a root node? True/False
    """

    class TreeNode:
        def __init__(self, name: str):
            self.name = name
            self.children: Sequence(TreeNode) = []
            self.ahead = 0
            self.behind = 0
            self.title = ""
            self.hash = ""
            self.active = False
            self.root = False

        def __repr__(self) -> str:
            return self.name

    branches = gather_upstreams()  # branch_name: upstream_branch

    # Dictionary of branch_name: tree_node
    nodes = {branch: TreeNode(branch) for branch in branches}
    active_branch = current_branch()
    for branch, upstream in branches.items():
        node = nodes[branch]

        # Set node metadata
        node.behind = commit_count_difference(branch, upstream)
        node.ahead = commit_count_difference(upstream, branch)
        node.hash = latest_commit_hash(branch)
        node.title = latest_commit_title(branch)

        if branch == active_branch:
            node.active = True

        if upstream is not None and upstream in nodes.keys():
            parent = nodes[upstream]
            parent.children.append(node)
        else:
            node.root = True

    # Sort children lists by name
    for node in nodes.values():
        children = node.children
        children.sort(key=lambda x: x.name)

    return nodes


def flow():
    """
    Recursively re-bases from the current active branch down

    Uses the child branch's upstream as the parent to configure the rebase.
    """
    logging.debug("Running flow")

    # TODO improve printing, possible traversing width-first through tree.
    def recursive_rebase(node):
        for child in node.children:
            print(child.name, end="  ")
            result = rebase(node.name, child.name)

            if "CONFLICT" in result:
                print(result)
                exit()

            if node.children:
                recursive_rebase(child)

    parent = current_branch()
    root_node = upstream_tree()[parent]
    recursive_rebase(root_node)
    print("")
    checkout(parent)


def branch_tree_string() -> str:
    """
    Creates a simple tree based on branch upstream value.

    branch_no_upstream
    master
        ├─ test_branch
        │   ├─ fun_branch
        │   └─ test_two
        └─ test_zoo

    Additional information printed:
        - number of commits this branch is behind master
        - number of commits on this branch
        - latest commit title
        - latest commit hash

    Returns:
        String to be printed in terminal
    """

    table = []

    def fill_table(node, prefix="", is_first=False, is_last=True):
        # Color coding for active branch
        if node.active:
            node.name = TermString(node.name, "BOLD", "GREEN")

        # Pipe printing logic
        pipe = "" if is_first else prefix + ("└─ " if is_last else "├─ ")
        next_prefix = prefix + "    " if is_last else "│   "

        # commit count coloring
        if node.behind is None:
            node.behind = ""
        else:
            node.behind = TermString(-node.behind, "RED") if -node.behind < 0 else " 0"

        if node.ahead is None:
            node.ahead = ""
        else:
            node.ahead = (
                TermString(f"+{node.ahead}", "GREEN") if node.ahead > 0 else " 0"
            )

        table.append(
            [
                pipe,
                node.name,
                node.behind,
                node.ahead,
                node.title[:50],
                TermString(node.hash, "YELLOW"),
            ]
        )

        # Set up arguments and recursively call its self
        children_count = len(node.children)
        for i, child in enumerate(node.children):
            is_last = i == children_count - 1
            fill_table(child, next_prefix, False, is_last)

    # Gather upstream tree data and sort by children length and then name
    nodes = upstream_tree()
    roots = [node for node in nodes.values() if node.root]
    roots.sort(key=lambda x: (len(x.children), x.name))

    # Fill the table list with data
    for i, root in enumerate(roots):
        fill_table(root, is_first=True)

    # Find the maximum width of each column.  The len() + 2 is column padding
    column_widths = [max(len(item) + 2 for item in column) for column in zip(*table)]

    # Generate the output string
    output = ""
    for row_items in table:
        content_length = 0
        column_width = 0
        for i in range(len(row_items)):
            content_length = len(row_items[i])
            # first two columns are conjoined (pipe and branch name)
            if i == 1:
                column_width = column_widths[0] + column_widths[1]
                content_length += len(row_items[i - 1])
            # remaining columns are normal
            elif i > 1:
                column_width = column_widths[i]
            padding = min(column_width - content_length, column_width)
            output += str(row_items[i]) + " " * padding
        output += "\n"

    return output


def main(argv):
    logging.basicConfig(level=logging.INFO)

    # CLI construction
    parser = argparse.ArgumentParser(
        prog="Kevin's git tools",
        description="Some extra functions to make using git easier.",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose output"
    )

    # Sub parsers
    subparsers = parser.add_subparsers(title="Subcommands", dest="subcommand")
    branch_parser = subparsers.add_parser("branch", help="Branch tools")

    # Branch subparser
    branch_subparsers = branch_parser.add_subparsers(
        title="Branch Subcommands", dest="branch_subcommand"
    )
    branch_tree_parser = branch_subparsers.add_parser(
        "tree", help="Shows a branch tree"
    )
    branch_tree_parser = branch_subparsers.add_parser(
        "flow", help="Recursive rebase starting from the active branch"
    )

    # Arg parsing
    args = parser.parse_args(argv)

    # Execution
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.subcommand == "branch":
        if args.branch_subcommand == "tree":
            print(branch_tree_string())
        elif args.branch_subcommand == "flow":
            flow()
        else:
            branch_parser.print_help()
    else:
        parser.print_help()


if __name__ == "__main__":
    args = sys.argv[1:]
    main(args)
