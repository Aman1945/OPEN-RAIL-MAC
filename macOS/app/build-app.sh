#!/bin/bash
# Builds "Open Rails.app": the Open Rails menu as a native Mac app (Apple Silicon).
# Needs the Xcode Command Line Tools (swiftc). Usage: ./build-app.sh [output folder] [version]
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="${1:-$HERE/build}"
VERSION="${2:-1.4}"
APP="$OUT/Open Rails.app"

rm -rf "$APP" "$OUT/OpenRails.iconset"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources" "$OUT/OpenRails.iconset"

swiftc -O -target arm64-apple-macos12.0 "$HERE/OpenRailsMenu.swift" -o "$APP/Contents/MacOS/OpenRails" \
    -framework Cocoa -framework WebKit
cp "$HERE/../orts-menu.py" "$APP/Contents/Resources/orts-menu.py"

# The icon: the Open Rails logo (64 x 64) scaled to the sizes macOS wants.
for size in 16 32 64 128 256 512 1024; do
    sips -z $size $size "$HERE/logo.png" --out "$OUT/OpenRails.iconset/s$size.png" >/dev/null
done
cd "$OUT/OpenRails.iconset"
cp s16.png icon_16x16.png;      cp s32.png icon_16x16@2x.png
cp s32.png icon_32x32.png;      cp s64.png icon_32x32@2x.png
cp s128.png icon_128x128.png;   cp s256.png icon_128x128@2x.png
cp s256.png icon_256x256.png;   cp s512.png icon_256x256@2x.png
cp s512.png icon_512x512.png;   cp s1024.png icon_512x512@2x.png
rm s*.png
iconutil -c icns "$OUT/OpenRails.iconset" -o "$APP/Contents/Resources/AppIcon.icns"
rm -rf "$OUT/OpenRails.iconset"

cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleName</key><string>Open Rails</string>
  <key>CFBundleDisplayName</key><string>Open Rails</string>
  <key>CFBundleIdentifier</key><string>io.github.aman1945.openrails-mac</string>
  <key>CFBundleExecutable</key><string>OpenRails</string>
  <key>CFBundleIconFile</key><string>AppIcon</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>$VERSION</string>
  <key>CFBundleVersion</key><string>$VERSION</string>
  <key>LSMinimumSystemVersion</key><string>12.0</string>
  <key>NSHighResolutionCapable</key><true/>
  <key>NSPrincipalClass</key><string>NSApplication</string>
  <key>NSAppTransportSecurity</key><dict><key>NSAllowsLocalNetworking</key><true/></dict>
</dict></plist>
PLIST

codesign --force --sign - "$APP"   # an ad-hoc signature: Apple Silicon will not run unsigned programs
echo "Built: $APP"
