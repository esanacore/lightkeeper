// Android Gradle Plugin 9 compiles Kotlin itself (built-in Kotlin), so there
// is no separate Kotlin plugin to declare or keep in step.
plugins {
    id("com.android.application") version "9.5.0" apply false
}
