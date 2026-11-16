# AirHUD Godot

This branch is Godot 4.7.2-stable with one fix, used by the AirHUD headset app
(Meta Quest, Vulkan, OpenXR). Only its Android source template differs from
the official release; the editor and other templates are the official ones.

## The fix

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

## Building

`misc/airhud/build_android_template.sh` builds the arm64 release and debug
engines with the official template flags and swaps them into the official
`android_source.zip`; nothing else in it changes. Releases of this fork
attach that template, the unstripped engines and their SHA256 sums.
