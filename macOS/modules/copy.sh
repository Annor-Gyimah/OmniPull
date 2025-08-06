#!/bin/bash

SOURCE_BINARY="/Users/annorion/Desktop/untitled folder/aria2/src/aria2c"  # Replace with your actual build output path
TARGET_DIR="$HOME/Library/Application Support/OmniPull"

mkdir -p "$TARGET_DIR"
cp "$SOURCE_BINARY" "$TARGET_DIR/aria2c"
chmod +x "$TARGET_DIR/aria2c"

echo "aria2c copied to $TARGET_DIR/aria2c"
