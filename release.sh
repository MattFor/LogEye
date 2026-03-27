#!/usr/bin/env bash
set -euo pipefail

sleep_with_dots() {
  local total=${1:-15}
  local interval=3
  local elapsed=0

  while [ $elapsed -lt $total ]; do
    for dots in "." ".." "..."; do
      echo -ne "\rSleeping$dots "
      sleep 1
      elapsed=$((elapsed + 1))

      if [ $elapsed -ge $total ]; then
        break
      fi
    done
  done

  echo -e "\rDone waiting."
}

usage() {
  echo "Usage: $0 <version> <commit-message>"
  echo "Example: $0 1.2.0 \"Release 1.2.0\""
  exit 1
}

if [[ $# -lt 2 ]]; then
  usage
fi

GIT_ONLY=false

if [[ "${@: -1}" == "-git" ]]; then
  GIT_ONLY=true
  set -- "${@:1:$(($#-1))}"
fi

VERSION="$1"
shift
COMMIT_MSG="$*"

CHANGELOG_CONTENT=""

if [[ "$GIT_ONLY" == true ]]; then
  echo "==> Running in GIT-ONLY mode"
fi

if [[ -z "$VERSION" || -z "$COMMIT_MSG" ]]; then
  usage
fi

if [[ ! "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "Error: version must be in format X.Y.Z"
  exit 1
fi

for cmd in python twine git gh; do
  if ! command -v $cmd >/dev/null 2>&1; then
    echo "Error: $cmd not found in PATH"
    exit 1
  fi
done

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

if [[ ! -f pyproject.toml ]]; then
  echo "Error: pyproject.toml not found"
  exit 1
fi

if [[ "$GIT_ONLY" == true ]]; then
  if [[ -f CHANGELOG.md ]]; then
    CHANGELOG_CONTENT=$(awk -v ver="$VERSION" '
      $0 ~ "^## \\[" ver "\\]" {flag=1; next}
      $0 ~ "^## \\[" && flag {exit}
      flag
    ' CHANGELOG.md)
  else
    echo "Warning: CHANGELOG.md not found, release will have no notes"
  fi
fi

if [[ "$GIT_ONLY" == false ]]; then
  echo "==> Updating version to $VERSION"

  # Update pyproject.toml
  sed -i -E "s/version = \"[0-9]+\.[0-9]+\.[0-9]+\"/version = \"$VERSION\"/" pyproject.toml

  # Update README.md
  if [[ -f README.md ]]; then
    sed -i -E "s/Version [0-9]+\.[0-9]+\.[0-9]+/Version $VERSION/" README.md
  fi

  echo "==> Updating README badge cache"

  if [[ -f README.md ]]; then
    CACHE_BUST=$(date +%s)

    sed -i -E \
      "s|https://img.shields.io/pypi/v/logeye(\?[^)]*)?|https://img.shields.io/pypi/v/logeye?cachebust=$CACHE_BUST|g" \
      README.md
  fi

  echo "==> Extracting changelog"

  if [[ ! -f CHANGELOG.md ]]; then
    echo "Error: CHANGELOG.md not found"
    exit 1
  fi

  CHANGELOG_CONTENT=$(awk -v ver="$VERSION" '
    $0 ~ "^## \\[" ver "\\]" {flag=1; next}
    $0 ~ "^## \\[" && flag {exit}
    flag
  ' CHANGELOG.md)

  if [[ -z "$CHANGELOG_CONTENT" ]]; then
    echo "Error: Version $VERSION not found in CHANGELOG.md"
    exit 1
  fi

  echo "==> Running Ruff format"
  ruff format .

  echo "==> Running Ruff check"
  if ! ruff check .; then
    echo "Ruff reported issues"
  fi

  echo "==> Running basedpyright"

  PYRIGHT_OUTPUT=$(basedpyright logeye 2>&1 || true)
  SUMMARY=$(echo "$PYRIGHT_OUTPUT" | tail -n 1)

  echo "basedpyright: $SUMMARY"

 echo "==> Running tests"

  TEST_OUTPUT=$(pytest --maxfail=0 --disable-warnings -q 2>&1 || true)
  echo "$TEST_OUTPUT"

  PASSED=$(echo "$TEST_OUTPUT" | grep -oP '\d+(?= passed)' | head -1 || true)
  FAILED=$(echo "$TEST_OUTPUT" | grep -oP '\d+(?= failed)' | head -1 || true)
  XPASSED=$(echo "$TEST_OUTPUT" | grep -oP '\d+(?= xpassed)' | head -1 || true)

  PASSED=${PASSED:-0}
  FAILED=${FAILED:-0}
  XPASSED=${XPASSED:-0}

  TOTAL=$((PASSED + FAILED + XPASSED))

  if [[ $TOTAL -eq 0 ]]; then
    echo "No tests detected, aborting!"
    exit 1
  fi

  SUCCESS_RATE=$(awk "BEGIN {printf \"%.2f\", ($PASSED + $XPASSED)/$TOTAL * 100}")

  echo "==> Test success rate: $SUCCESS_RATE%"

  THRESHOLD=95

  if (( $(echo "$SUCCESS_RATE < $THRESHOLD" | bc -l) )); then
    echo "Test success rate below ${THRESHOLD}%! Aborting! Time to fix something..."
    exit 1
  else
    echo "Test success rate above ${THRESHOLD}, continuing..."
  fi

  echo "==> Cleaning old build artifacts"
  rm -rf dist build *.egg-info

  echo "==> Building package"
  python -m build

  echo "==> Uploading to PyPI"
  twine upload dist/*

  sleep_with_dots 15
fi

echo "==> Updating git index"
git add .

echo "==> Committing"
git commit -m "$COMMIT_MSG" || echo "Nothing to commit"

echo "==> Creating tag v$VERSION"
git tag -f "v$VERSION"

echo "==> Pushing commit and tags"
git push origin master --tags

echo "==> Creating GitHub release"

gh release create "v$VERSION" \
  --title "v$VERSION" \
  --notes "$CHANGELOG_CONTENT" \
  || echo "Release already exists, skipping"

echo "==> Done"