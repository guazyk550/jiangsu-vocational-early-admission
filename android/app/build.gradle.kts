import org.jetbrains.kotlin.gradle.dsl.JvmTarget

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
    id("org.jetbrains.kotlin.plugin.serialization")
}

android {
    namespace = "com.jsvocnav.app"
    compileSdk = 36

    defaultConfig {
        applicationId = "com.jsvocnav.app"
        minSdk = 24
        targetSdk = 36
        versionCode = 1
        versionName = "1.2.0"
        // 注：未使用 resourceConfigurations/localeFilters 收窄语言资源——
        // 部分 AGP 版本该 API 仍有差异，为保证任何环境都能构建，这里保持默认。
    }

    buildTypes {
        release {
            // 首版先不开混淆，便于排查线上问题；数据与逻辑均在本地，无额外体积压力
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro",
            )
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlin {
        compilerOptions {
            jvmTarget.set(JvmTarget.JVM_17)
        }
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }

    packaging {
        resources.excludes += setOf("/META-INF/{AL2.0,LGPL2.1}")
    }

    sourceSets["main"].assets.srcDirs("src/main/assets")
}

// 把桌面版维护的同一份 data/schools.json 同步进 APK 的 assets，
// 保证两端数据永远一致（数据文件仍由 tools/ 下的脚本生成与维护）。
val syncDataset by tasks.registering(Copy::class) {
    from(rootProject.layout.projectDirectory.file("../data/schools.json"))
    into(layout.projectDirectory.dir("src/main/assets"))
}

tasks.named("preBuild") { dependsOn(syncDataset) }

dependencies {
    implementation(platform("androidx.compose:compose-bom:2024.09.00"))
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-graphics")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-extended")
    implementation("androidx.activity:activity-compose:1.9.3")
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.7")
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.7.3")

    debugImplementation("androidx.compose.ui:ui-tooling")
}
