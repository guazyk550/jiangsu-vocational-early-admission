package com.jsvocnav.app.data

import android.content.Context

/**
 * 本地偏好：参照点配置 + 收藏 + 最近浏览。
 *
 * 用 SharedPreferences（零依赖、足够快），避免为一个小工具引入数据库。
 */
class LocalStore(context: Context) {

    private val prefs = context.getSharedPreferences("jsvocnav", Context.MODE_PRIVATE)

    // ------------------------------------------------------------------ 参照点
    var originName: String
        get() = prefs.getString(KEY_ORIGIN_NAME, null) ?: DEFAULT_ORIGIN_NAME
        set(value) = prefs.edit().putString(KEY_ORIGIN_NAME, value).apply()

    var originLatitude: Double
        get() = prefs.getFloat(KEY_ORIGIN_LAT, DEFAULT_ORIGIN_LAT.toFloat()).toDouble()
        set(value) = prefs.edit().putFloat(KEY_ORIGIN_LAT, value.toFloat()).apply()

    var originLongitude: Double
        get() = prefs.getFloat(KEY_ORIGIN_LON, DEFAULT_ORIGIN_LON.toFloat()).toDouble()
        set(value) = prefs.edit().putFloat(KEY_ORIGIN_LON, value.toFloat()).apply()

    val origin: Origin
        get() = Origin(originName, originLatitude, originLongitude)

    data class Origin(val name: String, val latitude: Double, val longitude: Double)

    // ------------------------------------------------------------------ 收藏
    fun favorites(): Set<String> =
        prefs.getStringSet(KEY_FAVORITES, emptySet())?.toSet() ?: emptySet()

    fun isFavorite(id: String): Boolean = id in favorites()

    /** 切换收藏，返回切换后是否已收藏 */
    fun toggleFavorite(id: String): Boolean {
        val current = favorites().toMutableSet()
        val favorite = if (id in current) {
            current.remove(id)
            false
        } else {
            current.add(id)
            true
        }
        prefs.edit().putStringSet(KEY_FAVORITES, current).apply()
        return favorite
    }

    // ------------------------------------------------------------ 最近浏览
    fun recent(): List<String> =
        prefs.getString(KEY_RECENT, "")?.split("|")?.filter { it.isNotBlank() } ?: emptyList()

    fun recordRecent(id: String) {
        val list = recent().filter { it != id }.toMutableList()
        list.add(0, id)
        prefs.edit().putString(KEY_RECENT, list.take(RECENT_LIMIT).joinToString("|")).apply()
    }

    // ------------------------------------------------------------------ 更新
    var updateUrl: String
        get() = prefs.getString(KEY_UPDATE_URL, "").orEmpty()
        set(value) = prefs.edit().putString(KEY_UPDATE_URL, value).apply()

    var lastUpdateResult: String
        get() = prefs.getString(KEY_LAST_UPDATE_RESULT, "").orEmpty()
        set(value) = prefs.edit().putString(KEY_LAST_UPDATE_RESULT, value).apply()

    companion object {
        const val DEFAULT_ORIGIN_NAME = "常州武进洛阳高级中学"
        const val DEFAULT_ORIGIN_LAT = 31.6467631
        const val DEFAULT_ORIGIN_LON = 120.082389
        private const val RECENT_LIMIT = 20

        private const val KEY_ORIGIN_NAME = "origin_name"
        private const val KEY_ORIGIN_LAT = "origin_lat"
        private const val KEY_ORIGIN_LON = "origin_lon"
        private const val KEY_FAVORITES = "favorites"
        private const val KEY_RECENT = "recent"
        private const val KEY_UPDATE_URL = "update_url"
        private const val KEY_LAST_UPDATE_RESULT = "last_update_result"
    }
}
