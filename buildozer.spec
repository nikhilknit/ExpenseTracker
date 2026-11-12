[app]

# (str) Title of your application
title = Smart Expense Tracker

# (str) Package name
package.name = expensetracker

# (str) Package domain (needed for android/ios packaging)
package.domain = org.personal.expense

# (str) Source code where the main.py lives
source.dir = .

# (list) Source code extensions to include
source.include_exts = py,png,jpg,kv,atlas,json

# (list) List of inclusions using pattern matching
source.include_patterns = assets/*,src/*,tests/sample_sms.json

# (str) Application versioning
version = 1.0.0

# (list) Application requirements
# comma separated e.g. requirements = sqlite3,kivy
requirements = python3,kivy==2.3.0,kivymd==1.2.0,pillow,pyjnius,sqlite3

# (str) Supported orientation (one of landscape, sensorLandscape, portrait or all)
orientation = portrait

# (list) Permissions
android.permissions = READ_SMS,RECEIVE_SMS

# (int) Target Android API, should be as high as possible.
android.api = 33

# (int) Minimum API your APK will support.
android.minapi = 26

# (int) Android SDK version to use
# android.sdk = 33

# (str) Android NDK version to use
android.ndk = 25b

# (str) python-for-android branch to use
p4a.branch = v2024.01.21

# (bool) If True, automatically accept SDK license agreements. Intended for CI/CD.
android.accept_sdk_license = True

# (bool) Use --private data storage (True) or --dir public storage (False)
android.private_storage = True

# (list) List of Java .jar files to add to the libs so that pyjnius can access
# their classes. Don't add jars that you do not need, since extra jars can slow
# down the build process.
# android.add_jars = foo.jar,bar.jar

# (list) Android architectures to build for (e.g. armeabi-v7a, arm64-v8a, x86, x86_64)
android.archs = arm64-v8a

# (bool) enables Android auto backup feature (Android API >=23)
android.allow_backup = True

# (str) The format used to package the app for release mode (aab or apk)
android.release_artifact = apk

[buildozer]

# (int) Log level (0 = error only, 1 = info, 2 = debug with output)
log_level = 2

# (int) Display warning if buildozer is run as root (0 = False, 1 = True)
warn_on_root = 1
