#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: $0 <catalog-directory> <source-sha>" >&2
  exit 2
}

fail() {
  echo "$1" >&2
  exit 1
}

if (( $# != 2 )); then
  usage
fi

if [[ ! -d "$1" ]]; then
  fail "Catalog artifact is missing: $1"
fi
candidate="$(cd -- "$1" && pwd -P)"
readonly candidate
readonly source_sha="$2"
if [[ ! "$source_sha" =~ ^[0-9a-f]{40}$ ]]; then
  fail "Source SHA must be a full Git commit SHA: $source_sha"
fi

readonly repository_root="$(git rev-parse --show-toplevel)"
if [[ "$candidate/" == "$repository_root/"* ]]; then
  fail "Catalog directory must be outside the repository: $candidate"
fi

git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"

if [[ "$(git rev-parse --is-shallow-repository)" == true ]]; then
  git fetch --no-tags --filter=blob:none --unshallow origin main
else
  git fetch --no-tags --filter=blob:none origin main
fi

published_source_sha=""
artifact_ref="$(git ls-remote --heads origin refs/heads/artifacts)"
if [[ -n "$artifact_ref" ]]; then
  git fetch --no-tags --depth=1 origin artifacts
  git switch --force-create artifacts FETCH_HEAD
  published_subject="$(git log -1 --format=%s)"
  if [[ ! "$published_subject" =~ ^Publish\ artifacts\ for\ ([0-9a-f]{40})$ ]]; then
    fail "Artifact branch has an unexpected commit message: $published_subject"
  fi

  published_source_sha="${BASH_REMATCH[1]}"
  if [[ "$source_sha" != "$published_source_sha" ]]; then
    if git merge-base --is-ancestor "$source_sha" "$published_source_sha"; then
      echo "Skipping stale artifact publication for $source_sha"
      exit 0
    fi
    if ! git merge-base --is-ancestor "$published_source_sha" "$source_sha"; then
      fail "Published source $published_source_sha is not an ancestor of $source_sha"
    fi
  fi
else
  git switch --orphan artifacts
fi

git rm -r --quiet --ignore-unmatch .
cp -R "$candidate/." .
git add --all
if git diff --cached --quiet && [[ "$source_sha" == "$published_source_sha" ]]; then
  echo "Artifacts are already current"
  echo "Artifact commit: $(git rev-parse HEAD)"
  exit 0
fi

# Record the newest successful source even when its artifacts are unchanged.
git commit --allow-empty -m "Publish artifacts for $source_sha"
git push origin HEAD:artifacts
echo "Artifact commit: $(git rev-parse HEAD)"
