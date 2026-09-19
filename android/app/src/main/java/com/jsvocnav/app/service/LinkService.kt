package com.jsvocnav.app.service

import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.util.Log
import com.jsvocnav.app.data.LocalStore
import com.jsvocnav.app.data.School

/**
 * 打开外部链接 / 唤起地图。
 *
 * 策略与桌面版一致：**不内置浏览器**，交给系统（或用户装的地图 App）。
 * 地图优先唤起百度地图 App（如果安装了），否则回落到百度地图网页版。
 */
object LinkService {

    private const val TAG = "LinkService"
    private const val SRC = "android.jsvocnav"

    /** 打开普通链接；返回是否成功唤起 */
    fun openUrl(context: Context, url: String): Boolean {
        if (url.isBlank()) return false
        val uri = try {
            Uri.parse(url)
        } catch (e: Exception) {
            Log.w(TAG, "非法 URL: $url", e)
            return false
        }
        if (uri.scheme?.lowercase() !in listOf("http", "https")) return false
        return startView(context, uri)
    }

    /** 打开「参照点 → 该校」的驾车路线：先试百度地图 App，再回落网页版 */
    fun openRoute(context: Context, origin: LocalStore.Origin, school: School): Boolean {
        val appIntent = Intent(Intent.ACTION_VIEW, buildBaiduAppUri(origin, school)).apply {
            setPackage("com.baidu.BaiduMap")
        }
        if (tryStart(context, appIntent)) return true
        return openUrl(context, buildBaiduWebUrl(origin, school))
    }

    // ------------------------------------------------------------------ URL
    /** 百度地图 App 的 URI（coord_type=wgs84，让百度自己把我们用的 WGS84 坐标转成 BD09） */
    fun buildBaiduAppUri(origin: LocalStore.Origin, school: School): Uri {
        val builder = Uri.Builder()
            .scheme("baidumap")
            .authority("map")
            .appendPath("direction")
            .appendQueryParameter("origin", placeParam(origin.name, origin.latitude, origin.longitude))
            .appendQueryParameter("destination", placeParam(school.name, school.latitude, school.longitude))
            .appendQueryParameter("mode", "driving")
            .appendQueryParameter("coord_type", "wgs84")
            .appendQueryParameter("src", SRC)
        return builder.build()
    }

    /** 百度地图网页版路线（与桌面版完全一致的参数形态） */
    fun buildBaiduWebUrl(origin: LocalStore.Origin, school: School): String {
        val params = linkedMapOf(
            "origin" to placeParam(origin.name, origin.latitude, origin.longitude),
            "destination" to placeParam(school.name, school.latitude, school.longitude),
            "mode" to "driving",
            "region" to "江苏",
            "output" to "html",
            "src" to SRC,
        )
        return "https://api.map.baidu.com/direction?" +
            params.entries.joinToString("&") { "${it.key}=${Uri.encode(it.value)}" }
    }

    /** 地点搜索（无坐标时的降级方案） */
    fun buildBaiduSearchUrl(school: School): String {
        val keyword = listOf(school.name, school.address).filter { it.isNotBlank() }.joinToString(" ")
        return "https://map.baidu.com/search/${Uri.encode(keyword)}?querytype=s&wd=${Uri.encode(keyword)}&region=江苏&src=$SRC"
    }

    private fun placeParam(name: String, latitude: Double?, longitude: Double?): String =
        if (latitude != null && longitude != null) "latlng:$latitude,$longitude|name:$name" else name

    // ------------------------------------------------------------------ 内部
    private fun startView(context: Context, uri: Uri): Boolean =
        tryStart(context, Intent(Intent.ACTION_VIEW, uri))

    private fun tryStart(context: Context, intent: Intent): Boolean = try {
        context.startActivity(intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        true
    } catch (e: ActivityNotFoundException) {
        Log.w(TAG, "没有可处理该 Intent 的应用: ${intent.data}", e)
        false
    } catch (e: Exception) {
        Log.w(TAG, "启动失败", e)
        false
    }
}
