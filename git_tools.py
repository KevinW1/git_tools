import argparse
import logging
import subprocess
import sys


class term_colors:
    """
    Class for terminal colors

    Usage:
        {color}{your_text}{END}
        Example: f"{GREEN}{Hello World}{END}"
    """

    GREEN = "\033[92m"
    BOLD = "\033[1m"
    END = "\033[0m"


def exe_cmd(cmd):
    """
    executes a command in the shell and returns the output
    """
    return subprocess.run(cmd, capture_output=True, text=True, shell=True).stdout


def current_branch():
    """
    Returns the current branch
    """
    cmd = ["git rev-parse --abbrev-ref HEAD"]
    return exe_cmd(cmd).splitlines()[0]


def upstream_tree():
    """
    Constructs a simple tree based on each branches upstream branch.

    Yes this is a messy way to do it.  I'll fix it when it's worth the time.

    Returns:
        Dict in the form "branch_name": "node" where node contains:
            node.name - same as branch name in the dict
            node.children - nodes that consider this node an upstream parent
            node.active - is this the current branch? True/False
            node.root - is this a root node? True/False
    """

    class TreeNode:
        def __init__(self, name):
            self.name = name
            self.children = []
            self.active = False
            self.root = False

        def __repr__(self):
            return self.name

    cmd = [
        "git for-each-ref --format='%(refname:short) %(upstream:short)' refs/heads",
    ]
    result = exe_cmd(cmd)

    # Dictionary of branch_name: upstream_branch
    tree_data = {}
    for line in result.splitlines():
        split = line.split(" ")
        branch = split[0]
        upstream = split[1]

        # Empty string is considered to have no upstream
        # "origin/" upstreams are also considered to have none (e.g. main/master)
        if upstream == "" or upstream.startswith("origin/"):
            upstream = None

        tree_data[branch] = upstream

    # Dictionary of branch_name: tree_node
    nodes = {branch: TreeNode(branch) for branch in tree_data}
    active_branch = current_branch()
    for branch, upstream in tree_data.items():
        node = nodes[branch]
        if branch == active_branch:
            node.active = True
        if upstream is not None:
            parent = nodes[upstream]
            parent.children.append(node)
        else:
            node.root = True

    # Sort children lists by name
    for node in nodes.values():
        children = node.children
        children.sort(key=lambda x: x.name)

    return nodes


def print_branch_tree():
    """
    Prints a simple tree based on branch upstream value.  SImilar to linux tree command.

    branch_no_upstream
    master
        ├─ test_branch
        │   ├─ fun_branch
        │   └─ test_two
        └─ test_zoo

    """

    def print_tree(node, prefix="", is_first=False, is_last=True):
        # Color coding for active branch
        if node.active:
            name = f"{term_colors.BOLD}{term_colors.GREEN}{node.name}{term_colors.END}"
        else:
            name = node.name

        # Pipe printing logic
        if is_first:
            print(name)
        else:
            print(prefix + ("└─ " if is_last else "├─ ") + name)
        prefix += "    " if is_last else "│   "
        children_count = len(node.children)
        for i, child in enumerate(node.children):
            is_last = i == children_count - 1
            print_tree(child, prefix, False, is_last)

    # Gathers data
    nodes = upstream_tree()
    roots = [node for node in nodes.values() if node.root]
    # Sort by children length and then name
    roots.sort(key=lambda x: (len(x.children), x.name))

    # Print the tree
    for i, root in enumerate(roots):
        print_tree(root, is_first=True)


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
            print_branch_tree()
        elif args.branch_subcommand == "flow":
            print("TODO")
        else:
            branch_parser.print_help()
    else:
        parser.print_help()


if __name__ == "__main__":
    args = sys.argv[1:]
    main(args)
