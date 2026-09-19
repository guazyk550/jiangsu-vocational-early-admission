package com.jsvocnav.app.service

import com.jsvocnav.app.data.LocalStore
import com.jsvocnav.app.data.SchoolRepository
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.net.HttpURLConnection
import java.net.URL

/**
 * 数据更新（可选）。
 *
 * 硬约束（与桌面版一致）：
 * - 未配置地址时**完全不联网**；
 * - 网络失败 / 数据非法 / 数据为空 → **保留本地数据**，只返回提示；
 * - 只有解析成功且非空才会覆盖本地数据文件。
 */
object UpdateService {

    suspend fun check(repository: SchoolRepository, store: LocalStore): String =
        withContext(Dispatchers.IO) {
            val url = store.updateUrl.trim()
            if (url.isBlank()) {
                return@withContext "未配置数据更新地址（桌面版 README 有说明）"
            }
            if (!url.startsWith("http://") && !url.startsWith("https://")) {
                return@withContext "更新地址格式不正确"
            }

            val text = try {
                val connection = (URL(url).openConnection() as HttpURLConnection).apply {
                    connectTimeout = 10_000
                    readTimeout = 15_000
                    requestMethod = "GET"
                    setRequestProperty("User-Agent", "jsvocnav-android/1.1")
                    setRequestProperty("Cache-Control", "no-cache")
                }
                connection.inputStream.bufferedReader(Charsets.UTF_8).use { it.readText() }
            } catch (e: Exception) {
                store.lastUpdateResult = "网络失败：${e.message}"
                return@withContext "网络请求失败，已继续使用本地数据"
            }

            val ok = repository.writeExternal(text)
            val message = if (ok) "数据已更新" else "远程数据无效或为空，已保留本地数据"
            store.lastUpdateResult = message
            message
        }
}
