// The Lightkeeper companion app: framework Views over the firmware's own C++
// rules and panel rasterizer, reached through JNI (src/main/cpp). No AndroidX,
// no Compose, and no library in the APK beyond the Kotlin standard library
// that every Kotlin app carries. JUnit and the AndroidX test runner are test
// dependencies only and never ship.

import javax.inject.Inject

plugins {
    id("com.android.application")
}

// apps/android/app -> apps/android -> apps -> the repository root. The spec
// vectors and the brand files are read from there, never copied by hand.
val repoRoot: File = rootDir.parentFile.parentFile

android {
    namespace = "com.esanacore.lightkeeper"
    compileSdk = 36
    ndkVersion = "28.2.13676358"

    defaultConfig {
        applicationId = "com.esanacore.lightkeeper"
        minSdk = 26
        targetSdk = 36
        versionCode = 1
        versionName = "0.2.0"
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        ndk {
            // Phones (64- and 32-bit ARM) and the x86_64 emulator.
            abiFilters += listOf("arm64-v8a", "armeabi-v7a", "x86_64")
        }
        externalNativeBuild {
            cmake {
                // The firmware libraries need the C library only: no C++ runtime.
                arguments += "-DANDROID_STL=none"
            }
        }
    }

    externalNativeBuild {
        cmake {
            path = file("src/main/cpp/CMakeLists.txt")
            version = "3.22.1"
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    lint {
        abortOnError = true
        checkAllWarnings = true
        warningsAsErrors = false
        lintConfig = file("lint.xml")
    }

    testOptions {
        unitTests.all { test ->
            // The JVM tests read tokens.json, the spec vectors and this app's
            // colour resources straight from the checkout.
            test.systemProperty("lightkeeper.repoRoot", repoRoot.absolutePath)
            test.inputs.file(repoRoot.resolve("assets/brand/tokens.json"))
            test.inputs.file(repoRoot.resolve("spec/display_vectors.json"))
            test.inputs.dir(file("src/main/res"))
        }
    }
}

dependencies {
    testImplementation("junit:junit:4.13.2")
    androidTestImplementation("junit:junit:4.13.2")
    androidTestImplementation("androidx.test:runner:1.7.0")
}

/**
 * Copies files from the checkout into a generated source folder, under
 * `into`, each renamed by `renames` (by file name) when it has an entry.
 */
abstract class CopyRepoFiles @Inject constructor(private val fs: FileSystemOperations) :
    DefaultTask() {
    @get:InputFiles
    @get:PathSensitive(PathSensitivity.NAME_ONLY)
    abstract val sources: ConfigurableFileCollection

    @get:Input
    abstract val into: Property<String>

    @get:Input
    abstract val renames: MapProperty<String, String>

    @get:OutputDirectory
    abstract val outputDir: DirectoryProperty

    @TaskAction
    fun copy() {
        val folder = into.get()
        val names = renames.get()
        fs.sync {
            into(outputDir)
            from(sources) {
                into(folder)
                rename { original -> names[original] ?: original }
            }
        }
    }
}

// The launcher icon is the brand icon, pixel for pixel (assets/brand/png),
// and the mono mark for the themed (monochrome) icon.
val brandIcon = tasks.register<CopyRepoFiles>("copyBrandIcon") {
    sources.from(
        repoRoot.resolve("assets/brand/png/app-icon.png"),
        repoRoot.resolve("assets/brand/png/lightkeeper-mark-mono.png"),
    )
    into.set("drawable-nodpi")
    renames.put("app-icon.png", "lk_app_icon.png")
    renames.put("lightkeeper-mark-mono.png", "lk_app_icon_mono.png")
    outputDir.set(layout.buildDirectory.dir("generated/lightkeeper/brand-res"))
}

// The instrumented tests run every shared vector through JNI, read from the
// repository's spec/ folder at build time.
val specAssets = tasks.register<CopyRepoFiles>("copySpecVectors") {
    sources.from(
        repoRoot.resolve("spec/display_vectors.json"),
        repoRoot.resolve("spec/panel_vectors.json"),
        repoRoot.resolve("spec/response_vectors.json"),
    )
    into.set("spec")
    renames.set(emptyMap())
    outputDir.set(layout.buildDirectory.dir("generated/lightkeeper/spec-assets"))
}

androidComponents {
    onVariants { variant ->
        variant.sources.res?.addGeneratedSourceDirectory(brandIcon, CopyRepoFiles::outputDir)
        variant.deviceTests["AndroidTest"]
            ?.sources
            ?.assets
            ?.addGeneratedSourceDirectory(specAssets, CopyRepoFiles::outputDir)
    }
}
