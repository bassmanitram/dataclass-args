#!/usr/bin/env bash
# Decide whether commit <sha> should be tagged as a release.
#
# Usage: scripts/release_tag_check.sh <sha>
#
# Prints "tag=v<version>" when the project version at <sha> has no v<version>
# tag yet and is greater than every existing v<MAJOR>.<MINOR>.<PATCH> tag, or
# "tag=" when there is nothing to do (the reason goes to stderr). The decision
# does not depend on parent commits, so it works for merge, squash and rebase
# merges, and for pushes of several commits. When $GITHUB_OUTPUT is set, "tag="
# and "reason=" are appended to it. Exits 1 on a consistency error (non-numeric
# version, __version__ mismatch, missing CHANGELOG entry, non-increasing
# version) and 2 on bad usage.
set -euo pipefail

readonly PYPROJECT="pyproject.toml"
readonly INIT_FILE="dataclass_args/__init__.py"
readonly CHANGELOG="CHANGELOG.md"
readonly VERSION_RE='^[0-9]+\.[0-9]+\.[0-9]+$'

die() {
    echo "error: $*" >&2
    exit 1
}

# emit <tag> <reason>: report the decision and exit successfully.
emit() {
    local tag="$1" reason="$2"
    echo "$reason" >&2
    echo "tag=$tag"
    if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
        {
            echo "tag=$tag"
            echo "reason=$reason"
        } >>"$GITHUB_OUTPUT"
    fi
    exit 0
}

# project_version <rev>: print project.version from pyproject.toml at <rev>,
# or nothing when the file or the key is absent.
project_version() {
    local rev="$1" content
    content=$(git show "$rev:$PYPROJECT" 2>/dev/null) || return 0
    python3 -c '
import sys, tomllib
print(tomllib.loads(sys.stdin.read()).get("project", {}).get("version", ""))
' <<<"$content"
}

# module_version <rev>: print __version__ from the package __init__ at <rev>.
module_version() {
    local rev="$1" content
    content=$(git show "$rev:$INIT_FILE" 2>/dev/null) ||
        die "$INIT_FILE not found at $rev"
    python3 -c '
import re, sys
match = re.search(r"^__version__\s*=\s*[\"\x27]([^\"\x27]+)[\"\x27]", sys.stdin.read(), re.M)
print(match.group(1) if match else "")
' <<<"$content"
}

# highest_release_tag: print the highest v<MAJOR>.<MINOR>.<PATCH> tag, or nothing.
highest_release_tag() {
    git tag --list 'v*' |
        grep -E '^v[0-9]+\.[0-9]+\.[0-9]+$' |
        sort -t. -k1.2,1n -k2,2n -k3,3n |
        tail -n 1 || true
}

# version_gt <a> <b>: succeed when numeric version a is greater than b.
version_gt() {
    python3 -c '
import sys
parse = lambda v: tuple(int(p) for p in v.split("."))
sys.exit(0 if parse(sys.argv[1]) > parse(sys.argv[2]) else 1)
' "$1" "$2"
}

main() {
    [[ $# -eq 1 ]] || {
        echo "usage: $0 <sha>" >&2
        exit 2
    }
    local sha new module changelog highest
    sha=$(git rev-parse --verify "$1^{commit}") || die "unknown commit: $1"

    new=$(project_version "$sha")
    [[ -n "$new" ]] || die "no project.version in $PYPROJECT at $sha"

    if git rev-parse -q --verify "refs/tags/v$new" >/dev/null; then
        emit "" "tag v$new already exists"
    fi

    [[ "$new" =~ $VERSION_RE ]] ||
        die "version '$new' is not plain MAJOR.MINOR.PATCH"

    module=$(module_version "$sha")
    [[ "$module" == "$new" ]] ||
        die "version mismatch: $PYPROJECT has $new but $INIT_FILE __version__ is '$module'"

    changelog=$(git show "$sha:$CHANGELOG" 2>/dev/null) ||
        die "$CHANGELOG not found at $sha"
    grep -Eq "^## \\[${new//./\\.}\\]" <<<"$changelog" ||
        die "$CHANGELOG has no '## [$new]' heading"

    highest=$(highest_release_tag)
    if [[ -z "$highest" ]]; then
        emit "v$new" "first release"
    fi
    version_gt "$new" "${highest#v}" ||
        die "version $new is lower than or equal to the highest release tag $highest; tags must increase"
    emit "v$new" "$new > highest tag $highest"
}

main "$@"
