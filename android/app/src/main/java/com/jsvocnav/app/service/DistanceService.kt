package com.jsvocnav.app.service

import com.jsvocnav.app.data.LocalStore
import com.jsvocnav.app.data.School
import java.util.Locale
import kotlin.math.asin
import kotlin.math.cos
import kotlin.math.min
import kotlin.math.roundToInt
import kotlin.math.sin
import kotlin.math.sqrt

/**
 * 直线距离（Haversine 大圆距离）。
 *
 * ⚠️ 只算直线距离，**不是驾车距离**：界面文案里明确写「直线距离」，
 * 真正的驾车距离交给百度地图。
 */
object Geo {
    private const val EARTH_RADIUS_KM = 6371.0088

    fun haversine(lat1: Double, lon1: Double, lat2: Double, lon2: Double): Double {
        val phi1 = Math.toRadians(lat1)
        val phi2 = Math.toRadians(lat2)
        val dPhi = Math.toRadians(lat2 - lat1)
        val dLambda = Math.toRadians(lon2 - lon1)
        val a = sin(dPhi / 2).let { it * it } +
            cos(phi1) * cos(phi2) * sin(dLambda / 2).let { it * it }
        return 2 * EARTH_RADIUS_KM * asin(sqrt(min(1.0, a)))
    }

    fun formatKm(km: Double): String = String.format(Locale.CHINA, "%.1f", km)
}

class DistanceService(private val origin: LocalStore.Origin) {

    /** 院校到参照点的直线距离（公里）；任一端缺坐标返回 null */
    fun distanceKm(school: School): Double? {
        val lat = school.latitude ?: return null
        val lon = school.longitude ?: return null
        if (origin.latitude == 0.0 && origin.longitude == 0.0) return null
        return Geo.haversine(lat, lon, origin.latitude, origin.longitude)
    }

    fun describe(school: School): String {
        if (origin.latitude == 0.0 && origin.longitude == 0.0) return "暂无距离数据（参照点坐标缺失）"
        val km = distanceKm(school) ?: return "暂无距离数据（该校坐标缺失）"
        return "距离${origin.name}约 ${Geo.formatKm(km)} km（直线距离）"
    }

    /** `{school.id: 公里数}`，供「距离最近」排序使用 */
    fun distanceMap(schools: List<School>): Map<String, Double> =
        schools.mapNotNull { school -> distanceKm(school)?.let { school.id to it } }.toMap()

    /** 列表卡片上显示的短文本，如 `12.3 km` */
    fun shortText(school: School): String? =
        distanceKm(school)?.let { "${Geo.formatKm(it)} km" }
}

/** 筛选与排序（与桌面版规则一致） */
object SchoolQuery {

    fun filter(
        schools: List<School>,
        keyword: String,
        city: String,
        ownership: String,
        favoriteIds: Set<String>,
        recentIds: List<String> = emptyList(),
        scope: Scope = Scope.ALL,
    ): List<School> {
        val scoped = when (scope) {
            Scope.ALL -> schools
            Scope.FAVORITES -> schools.filter { it.id in favoriteIds }
            Scope.RECENT -> {
                val byId = schools.associateBy { it.id }
                recentIds.mapNotNull { byId[it] }
            }
        }
        val terms = keyword.trim().split(" ").filter { it.isNotBlank() }
        return scoped.filter { school ->
            if (city != ALL && school.city != city) return@filter false
            if (ownership != ALL && school.ownership != ownership) return@filter false
            if (terms.isEmpty()) return@filter true
            val blob = school.searchBlob().lowercase()
            terms.all { blob.contains(it.lowercase()) }
        }
    }

    fun sort(
        schools: List<School>,
        mode: com.jsvocnav.app.data.SortMode,
        distances: Map<String, Double>,
    ): List<School> = when (mode) {
        com.jsvocnav.app.data.SortMode.DEFAULT ->
            schools.sortedWith(compareBy({ it.city }, { it.name }))

        com.jsvocnav.app.data.SortMode.NAME -> schools.sortedBy { it.name }

        com.jsvocnav.app.data.SortMode.DISTANCE -> schools.sortedWith(
            compareBy({ distances[it.id] ?: Double.MAX_VALUE }, { it.city }, { it.name })
        )

        com.jsvocnav.app.data.SortMode.PUBLIC_FIRST -> schools.sortedWith(
            compareBy({ it.ownership != "公办" }, { it.city }, { it.name })
        )

        com.jsvocnav.app.data.SortMode.PRIVATE_FIRST -> schools.sortedWith(
            compareBy({ it.ownership != "民办" }, { it.city }, { it.name })
        )
    }

    const val ALL = "全部"
}

enum class Scope(val label: String) {
    ALL("全部院校"),
    FAVORITES("收藏"),
    RECENT("最近"),
}

/** 便捷：把距离四舍五入到一位小数（用于纯数值展示场景） */
fun Double.toOneDecimal(): Double = (this * 10).roundToInt() / 10.0
