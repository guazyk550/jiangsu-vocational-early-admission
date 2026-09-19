package com.jsvocnav.app.data

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/**
 * 一所院校的全部展示信息。
 *
 * 与桌面版 `data/schools.json` 字段一一对应。所有字段都有默认值，解析时容忍未知字段，
 * 因此数据文件里缺字段、写 null、出现新字段都不会导致崩溃。
 */
@Serializable
data class School(
    val id: String = "",
    val name: String = "",
    @SerialName("short_name") val shortName: String = "",
    val city: String = "",
    val district: String = "",
    val ownership: String = "",
    @SerialName("ownership_note") val ownershipNote: String = "",
    @SerialName("school_type") val schoolType: String = "",

    @SerialName("official_website") val officialWebsite: String = "",
    @SerialName("admission_website") val admissionWebsite: String = "",

    @SerialName("early_admission_url") val earlyAdmissionUrl: String = "",
    @SerialName("early_admission_title") val earlyAdmissionTitle: String = "",
    @SerialName("early_admission_year") val earlyAdmissionYear: Int? = null,
    @SerialName("early_admission_confidence") val earlyAdmissionConfidence: String = "none",
    @SerialName("early_admission_third_party") val earlyAdmissionThirdParty: Boolean = false,
    @SerialName("early_admission_is_section") val earlyAdmissionIsSection: Boolean = false,

    @SerialName("admission_brochure_url") val admissionBrochureUrl: String = "",
    @SerialName("admission_brochure_title") val admissionBrochureTitle: String = "",
    @SerialName("admission_plan_url") val admissionPlanUrl: String = "",
    @SerialName("admission_plan_title") val admissionPlanTitle: String = "",
    @SerialName("admission_result_url") val admissionResultUrl: String = "",
    @SerialName("admission_result_title") val admissionResultTitle: String = "",
    @SerialName("exam_material_url") val examMaterialUrl: String = "",
    @SerialName("exam_material_title") val examMaterialTitle: String = "",

    val address: String = "",
    val latitude: Double? = null,
    val longitude: Double? = null,
    @SerialName("coord_confidence") val coordConfidence: String = "none",
    @SerialName("coord_matched_name") val coordMatchedName: String = "",

    @SerialName("data_year") val dataYear: Int = 0,
    @SerialName("last_verified") val lastVerified: String = "",
    @SerialName("source_url") val sourceUrl: String = "",
    val notes: List<String> = emptyList(),
) {
    val hasCoordinates: Boolean
        get() = latitude != null && longitude != null

    /** 学校自有域名的提前招生页（第三方转载不算） */
    val hasOfficialEarlyAdmissionPage: Boolean
        get() = earlyAdmissionUrl.isNotBlank() && !earlyAdmissionThirdParty

    /** 主按钮应打开的链接：提前招生页 → 招生网 → 官网 */
    val admissionEntryUrl: String
        get() = when {
            hasOfficialEarlyAdmissionPage -> earlyAdmissionUrl
            admissionWebsite.isNotBlank() -> admissionWebsite
            else -> officialWebsite
        }

    /** 主按钮文案：区分「简章」与「栏目」，避免让用户以为点开的一定是当年度简章 */
    val admissionEntryLabel: String
        get() = when {
            hasOfficialEarlyAdmissionPage ->
                if (earlyAdmissionIsSection) "提前招生栏目" else "提前招生简章"

            admissionWebsite.isNotBlank() -> "打开招生网"
            officialWebsite.isNotBlank() -> "打开学校官网"
            else -> "暂无链接"
        }

    val ownershipText: String
        get() = if (ownershipNote.isBlank()) ownership else "$ownership（$ownershipNote）"

    fun searchBlob(): String = listOf(
        name, shortName, city, district, ownership, ownershipNote, schoolType, address,
    ).filter { it.isNotBlank() }.joinToString(" ")
}

@Serializable
data class DatasetMeta(
    @SerialName("data_year") val dataYear: Int = 0,
    @SerialName("generated_at") val generatedAt: String = "",
    @SerialName("last_verified") val lastVerified: String = "",
    val count: Int = 0,
    val scope: String = "",
    val disclaimer: String = "",
    val sources: List<String> = emptyList(),
)

@Serializable
data class Dataset(
    val meta: DatasetMeta = DatasetMeta(),
    val schools: List<School> = emptyList(),
)

/** 排序方式（与桌面版保持一致） */
enum class SortMode(val label: String, val shortLabel: String) {
    DEFAULT("默认（城市→校名）", "默认"),
    NAME("A-Z 校名", "A-Z"),
    DISTANCE("距离最近", "距离最近"),
    PUBLIC_FIRST("公办优先", "公办优先"),
    PRIVATE_FIRST("民办优先", "民办优先"),
}
