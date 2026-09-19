package com.jsvocnav.app.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Star
import androidx.compose.material.icons.outlined.StarBorder
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.jsvocnav.app.data.School

/** 列表里的院校卡片：校名 / 城市·办学性质 / 地址 / 距离 + 三个操作按钮 + 收藏 */
@Composable
fun SchoolCardView(
    school: School,
    distanceText: String?,
    isFavorite: Boolean,
    onToggleFavorite: () -> Unit,
    onOpenAdmission: () -> Unit,
    onOpenMap: () -> Unit,
    onDetail: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Card(
        modifier = modifier.fillMaxWidth(),
        shape = RoundedCornerShape(14.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
    ) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {

            // 校名 + 收藏
            Row(verticalAlignment = Alignment.Top) {
                Text(
                    text = school.name,
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold,
                    modifier = Modifier.weight(1f),
                )
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
            }

            // 城市 · 办学性质 · 类型 · 距离
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    text = school.city.ifBlank { "城市未知" },
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Spacer(Modifier.width(8.dp))
                OwnershipBadge(school)
                if (school.schoolType.isNotBlank()) {
                    Spacer(Modifier.width(8.dp))
                    Text(
                        text = school.schoolType,
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                if (distanceText != null) {
                    Spacer(Modifier.weight(1f))
                    Text(
                        text = "距目标校 $distanceText",
                        style = MaterialTheme.typography.bodyMedium,
                        fontWeight = FontWeight.SemiBold,
                        color = MaterialTheme.colorScheme.primary,
                    )
                }
            }

            // 地址
            Text(
                text = school.address.ifBlank { "地址暂无数据" },
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
            )

            if (school.earlyAdmissionThirdParty) {
                androidx.compose.material3.Surface(
                    color = MaterialTheme.colorScheme.errorContainer,
                    shape = RoundedCornerShape(6.dp),
                ) {
                    Text(
                        text = "简章为第三方转载",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onErrorContainer,
                        modifier = Modifier.padding(horizontal = 8.dp, vertical = 2.dp),
                    )
                }
            }

            // 操作按钮
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(
                    onClick = onOpenAdmission,
                    enabled = school.admissionEntryUrl.isNotBlank(),
                ) {
                    Text(school.admissionEntryLabel, maxLines = 1, overflow = TextOverflow.Ellipsis)
                }
                OutlinedButton(onClick = onOpenMap) { Text("百度地图") }
                OutlinedButton(onClick = onDetail) { Text("详情") }
            }
        }
    }
}

@Composable
fun OwnershipBadge(school: School) {
    val isPublic = school.ownership == "公办"
    val container = if (isPublic) {
        MaterialTheme.colorScheme.secondaryContainer
    } else {
        MaterialTheme.colorScheme.tertiaryContainer
    }
    val content = if (isPublic) {
        MaterialTheme.colorScheme.onSecondaryContainer
    } else {
        MaterialTheme.colorScheme.onTertiaryContainer
    }
    Surface(color = container, shape = RoundedCornerShape(6.dp)) {
        Text(
            text = school.ownershipText.ifBlank { "性质未知" },
            style = MaterialTheme.typography.labelMedium,
            color = content,
            modifier = Modifier.padding(horizontal = 8.dp, vertical = 2.dp),
        )
    }
}
