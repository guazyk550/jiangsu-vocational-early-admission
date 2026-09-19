package com.jsvocnav.app.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Star
import androidx.compose.material.icons.outlined.StarBorder
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.jsvocnav.app.data.School
import com.jsvocnav.app.service.DistanceService

/** 院校详情页：客观信息 + 全部官方入口 + 数据溯源 + 免责声明 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SchoolDetailScreen(
    school: School,
    distanceService: DistanceService,
    originName: String,
    isFavorite: Boolean,
    onToggleFavorite: () -> Unit,
    onOpenUrl: (String) -> Unit,
    onOpenMap: () -> Unit,
    onBack: () -> Unit,
) {
    val clipboard = LocalClipboardManager.current

    Scaffold(
        topBar = {
            TopAppBar(
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.surface,
                ),
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "返回")
                    }
                },
                title = {
                    Text(
                        text = school.name,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                        style = MaterialTheme.typography.titleMedium,
                    )
                },
                actions = {
                    IconButton(onClick = onToggleFavorite) {
                        Icon(
                            imageVector = if (isFavorite) Icons.Filled.Star else Icons.Outlined.StarBorder,
                            contentDescription = if (isFavorite) "取消收藏" else "收藏",
                            tint = if (isFavorite) {
                                MaterialTheme.colorScheme.tertiary
                            } else {
                                MaterialTheme.colorScheme.onSurfaceVariant
                            },
                        )
                    }
                },
            )
        },
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 16.dp, vertical = 12.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            // ---------------- 标题区 ----------------
            Text(
                text = school.name,
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.SemiBold,
            )
            Row(verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                Text(
                    text = school.city.ifBlank { "城市未知" },
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Spacer(Modifier.width(8.dp))
                OwnershipBadge(school)
            }

            // ---------------- 两个主按钮 ----------------
            Button(
                onClick = { onOpenUrl(school.admissionEntryUrl) },
                enabled = school.admissionEntryUrl.isNotBlank(),
                modifier = Modifier
                    .fillMaxWidth()
                    .height(48.dp),
            ) {
                Text(school.admissionEntryLabel, maxLines = 1, overflow = TextOverflow.Ellipsis)
            }
            OutlinedButton(
                onClick = onOpenMap,
                modifier = Modifier
                    .fillMaxWidth()
                    .height(48.dp),
            ) {
                Text("在百度地图中查看")
            }

            // ---------------- 其他官方入口 ----------------
            val entries = buildList {
                if (school.officialWebsite.isNotBlank()) add("学校官网" to school.officialWebsite)
                if (school.admissionWebsite.isNotBlank()) add("招生网" to school.admissionWebsite)
                if (school.admissionBrochureUrl.isNotBlank()) add("招生简章" to school.admissionBrochureUrl)
                if (school.admissionPlanUrl.isNotBlank()) add("招生计划" to school.admissionPlanUrl)
                if (school.admissionResultUrl.isNotBlank()) add("录取结果" to school.admissionResultUrl)
                if (school.examMaterialUrl.isNotBlank()) add("考试资料" to school.examMaterialUrl)
            }
            if (entries.isNotEmpty()) {
                Text(
                    text = "其他官方入口",
                    style = MaterialTheme.typography.labelLarge,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                entries.chunked(2).forEach { row ->
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        row.forEach { (label, url) ->
                            OutlinedButton(
                                onClick = { onOpenUrl(url) },
                                modifier = Modifier.weight(1f),
                            ) {
                                Text(label, maxLines = 1, overflow = TextOverflow.Ellipsis)
                            }
                        }
                        if (row.size == 1) Spacer(Modifier.weight(1f))
                    }
                }
            }

            // ---------------- 信息表 ----------------
            Card(
                colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
                modifier = Modifier.fillMaxWidth(),
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    FieldRow("学校简称", school.shortName)
                    FieldRow("所在城市", listOf(school.city, school.district).filter { it.isNotBlank() }.joinToString(" "))
                    FieldRow("办学性质", school.ownershipText)
                    FieldRow("学校类型", school.schoolType)
                    FieldRow("学校地址", school.address)
                    HorizontalDivider(Modifier.padding(vertical = 8.dp))
                    FieldRow("提前招生页", school.earlyAdmissionUrl.ifBlank { "未找到（将从招生网进入）" })
                    if (school.earlyAdmissionTitle.isNotBlank()) {
                        FieldRow("页面标题", school.earlyAdmissionTitle)
                    }
                    school.earlyAdmissionYear?.let { FieldRow("页面年度", "$it 年") }
                    FieldRow("页面核验", confidenceHint(school.earlyAdmissionConfidence))
                    FieldRow("招生简章", school.admissionBrochureUrl.ifBlank { "未收录" })
                    FieldRow("招生计划", school.admissionPlanUrl.ifBlank { "未收录" })
                    FieldRow("录取结果", school.admissionResultUrl.ifBlank { "未收录" })
                    FieldRow("考试资料", school.examMaterialUrl.ifBlank { "未收录" })
                    HorizontalDivider(Modifier.padding(vertical = 8.dp))
                    FieldRow("距参照点", distanceService.describe(school))
                    FieldRow(
                        "经纬度",
                        if (school.hasCoordinates) {
                            "%.6f, %.6f（置信度 %s，来源 OpenStreetMap，非官方数据）"
                                .format(school.latitude, school.longitude, school.coordConfidence)
                        } else {
                            "暂无坐标数据"
                        },
                    )
                    FieldRow("数据年份", if (school.dataYear > 0) "${school.dataYear} 年" else "暂无数据")
                    FieldRow("核验日期", school.lastVerified.ifBlank { "暂无数据" })
                    FieldRow("参照点", originName)
                }
            }

            // ---------------- 操作 ----------------
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(
                    onClick = {
                        clipboard.setText(AnnotatedString(buildShareText(school)))
                    },
                    modifier = Modifier.weight(1f),
                ) { Text("复制学校信息") }
                OutlinedButton(
                    onClick = { onOpenUrl(school.admissionEntryUrl) },
                    enabled = school.admissionEntryUrl.isNotBlank(),
                    modifier = Modifier.weight(1f),
                ) { Text("打开链接") }
            }

            // ---------------- 数据来源 + 免责声明 ----------------
            school.sourceUrl.takeIf { it.isNotBlank() }?.let { url ->
                Text(
                    text = "数据来源：$url",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.primary,
                    modifier = Modifier.fillMaxWidth(),
                )
            }
            Text(
                text = DISCLAIMER_FALLBACK,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            school.notes.firstOrNull()?.let { note ->
                Text(
                    text = "核验备注：$note",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Spacer(Modifier.height(16.dp))
        }
    }
}

@Composable
private fun FieldRow(label: String, value: String) {
    Row(modifier = Modifier
        .fillMaxWidth()
        .padding(vertical = 4.dp)) {
        Text(
            text = label,
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.width(84.dp),
        )
        Text(
            text = value.ifBlank { "暂无数据" },
            style = MaterialTheme.typography.bodyMedium,
            modifier = Modifier.weight(1f),
        )
    }
}

private fun confidenceHint(level: String): String = when (level) {
    "high" -> "已在官方站点核验页面含「提前招生」"
    "medium" -> "第三方转载页，或官方站点无法直连核验"
    "low" -> "仅搜索索引线索，未能实际打开验证"
    else -> "未找到明确页面"
}

private fun buildShareText(school: School): String = buildString {
    appendLine("学校名称：${school.name}")
    appendLine("学校简称：${school.shortName}")
    appendLine("所在城市：${school.city}")
    appendLine("办学性质：${school.ownershipText}")
    appendLine("学校类型：${school.schoolType}")
    appendLine("学校地址：${school.address.ifBlank { "暂无数据" }}")
    appendLine("官方网站：${school.officialWebsite.ifBlank { "暂无数据" }}")
    appendLine("招生网站：${school.admissionWebsite.ifBlank { "暂无数据" }}")
    appendLine("提前招生页：${school.earlyAdmissionUrl.ifBlank { "暂无数据" }}")
    appendLine("招生简章：${school.admissionBrochureUrl.ifBlank { "暂无数据" }}")
    appendLine("招生计划：${school.admissionPlanUrl.ifBlank { "暂无数据" }}")
    appendLine("录取结果：${school.admissionResultUrl.ifBlank { "暂无数据" }}")
    appendLine("考试资料：${school.examMaterialUrl.ifBlank { "暂无数据" }}")
    appendLine("数据年份：${if (school.dataYear > 0) school.dataYear else "暂无数据"}")
    appendLine()
    append(DISCLAIMER_FALLBACK)
}
