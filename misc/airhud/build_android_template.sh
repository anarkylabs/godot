#!/bin/bash
# Builds the AirHUD Android source template from this branch: the arm64
# release and debug engines, swapped into the stock android_source.zip of the
# same Godot version (misc/airhud/make_template.py).
#
#   misc/airhud/build_android_template.sh [stock android_source.zip]
#
# Without a stock template, the official export templates are downloaded and
# checked against the release's SHA512 sums. Needs ANDROID_HOME with the NDK
# version platform/android/detect.py names, Python 3 and SCons (on PATH, or
# with SCONS="python3 -m SCons" and PYTHONPATH set). JOBS sets the build jobs.
#
# Output in bin/airhud/: android_source.zip, the unstripped engines for crash
# symbolication, and SHA256SUMS.
set -euo pipefail
cd "$(dirname "$0")/../.."
STOCK=${1:-}
JOBS=${JOBS:-$(nproc)}
SCONS=${SCONS:-scons}
OUT=bin/airhud
VERSION=$(python3 -c 'import version; print(f"{version.major}.{version.minor}.{version.patch}-{version.status}" if version.patch else f"{version.major}.{version.minor}-{version.status}")')
NDK_VERSION=$(sed -n 's/^ *return "\([0-9.]*\)"$/\1/p' platform/android/detect.py | head -1)
NDK=$ANDROID_HOME/ndk/$NDK_VERSION
[ -d "$NDK" ] || { echo "NDK $NDK_VERSION not found under $ANDROID_HOME/ndk"; exit 1; }
STRIP=$NDK/toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-strip
mkdir -p "$OUT"

if [ -z "$STOCK" ]; then
  base=https://github.com/godotengine/godot-builds/releases/download/$VERSION
  templates=Godot_v${VERSION}_export_templates.tpz
  [ -f "$OUT/$templates" ] || curl -fL --retry 3 -o "$OUT/$templates" "$base/$templates"
  curl -fsSL -o "$OUT/SHA512-SUMS.txt" "$base/SHA512-SUMS.txt"
  (cd "$OUT" && grep " $templates\$" SHA512-SUMS.txt | sha512sum -c -)
  unzip -o -q -j "$OUT/$templates" templates/android_source.zip -d "$OUT/stock"
  STOCK=$OUT/stock/android_source.zip
fi

[ -f thirdparty/swappy-frame-pacing/arm64-v8a/libswappy_static.a ] || python3 misc/scripts/install_swappy_android.py

# The flags of the official Android templates; debug_symbols keeps an
# unstripped copy for symbolicating crashes.
for target in template_release template_debug; do
  $SCONS platform=android arch=arm64 target=$target production=yes debug_symbols=yes swappy=yes -j"$JOBS"
  kind=${target#template_}
  cp "platform/android/java/lib/libs/$kind/arm64-v8a/libgodot_android.so" "$OUT/libgodot_android.$kind.unstripped.so"
  # --strip-unneeded matches the size of the official libraries.
  "$STRIP" --strip-unneeded -o "$OUT/libgodot_android.$kind.so" "$OUT/libgodot_android.$kind.unstripped.so"
done

python3 misc/airhud/make_template.py "$STOCK" "$OUT/libgodot_android.release.so" \
  "$OUT/libgodot_android.debug.so" "$OUT/android_source.zip"
tar -C "$OUT" -cJf "$OUT/libgodot_android-arm64-symbols.tar.xz" \
  libgodot_android.release.unstripped.so libgodot_android.debug.unstripped.so
(cd "$OUT" && sha256sum android_source.zip libgodot_android-arm64-symbols.tar.xz > SHA256SUMS && cat SHA256SUMS)
