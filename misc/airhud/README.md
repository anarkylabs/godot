# AirHUD Godot

This branch is Godot 4.7.2-stable with one fix and one feature, used by the
AirHUD headset app (Meta Quest, Vulkan, OpenXR). Its releases attach the
Android source template and a macOS editor that knows the feature's API; the
other templates are the official ones.

## The fix: OpenXR queue lock

Godot's renderer and the OpenXR runtime share one Vulkan queue. Godot locks
its own submits to it (`submit_mutex` in the Vulkan driver), but the OpenXR
module calls `xrBeginFrame`, `xrEndFrame`, `xrAcquireSwapchainImage` and
`xrReleaseSwapchainImage` without that lock, although the OpenXR Vulkan
binding (`XR_KHR_vulkan_enable2`) requires the queue to be externally
synchronized during them. A texture created on a worker thread submits its
upload to the same queue (`RenderingDevice` transfer workers), and when that
overlaps one of those calls the driver's fence state breaks: "Couldn't wait
for Vulkan fence (VkResult error -3)", then a crash in `vkGetFenceStatus` or
`RenderingDevice::_free_pending_resources`.

The fix lets the OpenXR module hold the driver's lock on the queue it was
given during those four calls (`OpenXRGraphicsExtensionWrapper::lock_queue`).

On a Quest 3, three threads creating textures, meshes and glyph atlases
crashed the official engine within 8-49 s (3 of 3 runs); with the fix, 2 runs
of 5 minutes ran without a crash or fence error.

## The feature: hardware buffers in ExternalTexture

`ExternalTexture.submit_hardware_buffer()` takes an Android `AHardwareBuffer`
(a video decoder's output) and, at the start of the next draw, imports it into
Vulkan without a copy and converts it into an ordinary RGBA texture behind the
`ExternalTexture`. `RenderingDevice.SUPPORTS_ANDROID_HARDWARE_BUFFER` (14 in
this branch) reports support. This is upstream PR godotengine/godot#124376
(closed unmerged under the new-contributor rule, not on review), backported:
4.7.2 lacks some enum values it neighbours, counts texture memory as a plain
number and names the decal atlas call `decal_atlas_mark_dirty_on_texture`.
The app projects recorded drone video onto its map through it.

On a Quest 3 (Adreno 740), 1080p decoder frames at 30 Hz converted with no
errors over 2,800 submissions; handing a frame over costs about 0.4 ms of main
thread, and converting it about 0.21 ms of GPU. The first conversion of a
session builds its pipeline (one frame of about 19 ms).

`ExternalTexture.generate_mipmaps` (off by default) also gives the converted
texture a mip chain, so a frame seen from afar can be sampled with mipmap
filtering instead of shimmering. Godot's `RenderingDevice` has no image blit,
so each level is drawn from the one before with the renderer's own mipmap pass
(`CopyEffects::make_mipmap_raster` on the Mobile renderer, the compute version
on Forward+), through views of each level kept with the texture; the render
graph orders the passes and their barriers before any view samples the frame.
The crop is applied by the conversion, so no level sees padding rows.
On the Quest 3, the mip chain of a 1080p frame costs about 0.31 ms of GPU per
conversion, about 0.13 ms a frame on average with 30 fps video at 72 Hz. Its
11 levels make each texture 11.1 MB instead of 8.3 MB.

## Building

`misc/airhud/build_android_template.sh` builds the arm64 release and debug
engines with the official template flags and swaps them into the official
`android_source.zip`; nothing else in it changes. The `AirHUD macOS editor`
workflow, run for each release tag, builds the universal production editor and
packages it as an ad-hoc signed `Godot.app`. Releases of this fork attach the
template, the unstripped engines, the editor and their SHA256 sums.
