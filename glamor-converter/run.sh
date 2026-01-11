#!/usr/bin/env bash

set -e

INPUT_DIR="/media/nvme7n1/l/jm/GLaMoR/data/triples"
OUTPUT_DIR="/media/nvme7n1/l/jm/GLaMoR/data/mid"

echo "[INFO] Building Maven project..."
mvn -q package

JAR="target/glamor-converter-1.0-SNAPSHOT-shaded.jar"

echo "[INFO] Using JAR: $JAR"

for file in "$INPUT_DIR"/*.jsonl; do
    [ -e "$file" ] || continue

    BASENAME=$(basename "$file" .jsonl)
    echo "[INFO] Processing $BASENAME.jsonl"

    java -jar "$JAR" --input "$file" --output "$OUTPUT_DIR" --base "$BASENAME"

    echo "[DONE] $BASENAME"
done

echo "[ALL DONE]"

