# AirHUD Godot

This branch is Godot 4.7.2-stable with one fix and one feature, used by the
AirHUD headset app (Meta Quest, Vulkan, OpenXR). Only its Android source
template differs from the official release; the editor and other templates are
the official ones.

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
thread and no measurable GPU time. The first conversion of a session builds its
pipeline (one frame of about 19 ms).

## Building

`misc/airhud/build_android_template.sh` builds the arm64 release and debug
engines with the official template flags and swaps them into the official
`android_source.zip`; nothing else in it changes. Releases of this fork
attach that template, the unstripped engines and their SHA256 sums.
