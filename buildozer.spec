[app]
title = Stoixima
package.name = stoixima
package.domain = gr.stoixima
source.dir = .
source.include_exts = py
source.exclude_dirs = .github, bin, .buildozer
version = 1.0
requirements = python3,kivy==2.3.1,certifi
orientation = portrait
fullscreen = 0
android.permissions = INTERNET
android.api = 34
android.minapi = 24
android.archs = arm64-v8a
android.accept_sdk_license = True
android.allow_backup = True

[buildozer]
log_level = 2
warn_on_root = 0
