// The Lightkeeper Android companion app (apps/android/README.md). One module,
// :app. Plugins and test libraries come from Google's Maven and Maven Central;
// the app itself ships no third-party library (docs/OTS_SOFTWARE.md).

pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
    }
}

rootProject.name = "lightkeeper-android"
include(":app")
