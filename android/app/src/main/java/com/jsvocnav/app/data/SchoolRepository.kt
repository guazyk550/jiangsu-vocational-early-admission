package com.jsvocnav.app.data

import android.content.Context
import android.util.Log
import kotlinx.serialization.json.Json
import java.io.File

/**
 * 数据仓储。
 *
 * 读取顺序（与桌面版一致，保证「只换 JSON、不重装 App」可行）：
 * 1. App 私有目录 `filesDir/schools.json`（数据更新写入这里）
 * 2. APK 内置 `assets/schools.json`
 *
 * 任何解析失败都会降级到下一个来源，绝不因为数据问题崩溃。
 */
class SchoolRepository(private val context: Context) {

    private val json = Json {
        ignoreUnknownKeys = true
        isLenient = true
        coerceInputValues = true
        explicitNulls = false
    }

    private var cached: LoadResult? = null

    data class LoadResult(
        val dataset: Dataset,
        val source: String,
        val warning: String? = null,
    ) {
        val schools: List<School> get() = dataset.schools
    }

    fun load(force: Boolean = false): LoadResult {
        cached?.let { if (!force) return it }

        val external = File(context.filesDir, FILE_NAME)
        if (external.exists()) {
            parse(external.readText(Charsets.UTF_8))?.let {
                return LoadResult(it, "外部数据文件").also { result -> cached = result }
            }
            Log.w(TAG, "外部数据文件解析失败，回退到内置数据")
        }

        return try {
            val text = context.assets.open(FILE_NAME).bufferedReader(Charsets.UTF_8).use { it.readText() }
            val dataset = json.decodeFromString(Dataset.serializer(), text)
            LoadResult(dataset, "内置数据").also { cached = it }
        } catch (e: Exception) {
            Log.e(TAG, "内置数据读取失败", e)
            LoadResult(Dataset(), "无可用数据", "数据加载失败：${e.message}")
                .also { cached = it }
        }
    }

    private fun parse(text: String): Dataset? = try {
        json.decodeFromString(Dataset.serializer(), text)
            .takeIf { it.schools.isNotEmpty() }
    } catch (e: Exception) {
        Log.w(TAG, "解析失败", e)
        null
    }

    /** 写入外部数据文件（数据更新用）；失败返回 false 且不动原文件 */
    fun writeExternal(text: String): Boolean {
        val parsed = parse(text) ?: return false
        return try {
            File(context.filesDir, FILE_NAME).writeText(text, Charsets.UTF_8)
            cached = LoadResult(parsed, "外部数据文件")
            true
        } catch (e: Exception) {
            Log.e(TAG, "写入外部数据失败", e)
            false
        }
    }

    companion object {
        private const val TAG = "SchoolRepository"
        const val FILE_NAME = "schools.json"
    }
}
