#!/bin/bash
# Strip simulator architectures from embedded frameworks for App Store submission
APP_PATH="${TARGET_BUILD_DIR}/${WRAPPER_NAME}"

find "$APP_PATH" -name '*.framework' -type d | while read -r FRAMEWORK
do
    FRAMEWORK_EXECUTABLE_NAME=$(defaults read "$FRAMEWORK/Info.plist" CFBundleExecutable 2>/dev/null)
    if [ -z "$FRAMEWORK_EXECUTABLE_NAME" ]; then
        continue
    fi
    FRAMEWORK_EXECUTABLE_PATH="$FRAMEWORK/$FRAMEWORK_EXECUTABLE_NAME"
    if [ ! -f "$FRAMEWORK_EXECUTABLE_PATH" ]; then
        continue
    fi

    ARCHS_IN_BINARY=$(lipo -archs "$FRAMEWORK_EXECUTABLE_PATH" 2>/dev/null)
    
    if echo "$ARCHS_IN_BINARY" | grep -q "x86_64"; then
        echo "Stripping x86_64 from $FRAMEWORK_EXECUTABLE_NAME"
        lipo -remove x86_64 "$FRAMEWORK_EXECUTABLE_PATH" -output "$FRAMEWORK_EXECUTABLE_PATH" 2>/dev/null || true
    fi
    
    # Also check for simulator arm64 (iossimulator)
    if file "$FRAMEWORK_EXECUTABLE_PATH" | grep -q "Simulator"; then
        echo "Found simulator slice in $FRAMEWORK_EXECUTABLE_NAME, stripping..."
        # Extract only the ios arm64 slice
        lipo -thin arm64 "$FRAMEWORK_EXECUTABLE_PATH" -output "${FRAMEWORK_EXECUTABLE_PATH}.tmp" 2>/dev/null
        if [ -f "${FRAMEWORK_EXECUTABLE_PATH}.tmp" ]; then
            mv "${FRAMEWORK_EXECUTABLE_PATH}.tmp" "$FRAMEWORK_EXECUTABLE_PATH"
        fi
    fi
done
