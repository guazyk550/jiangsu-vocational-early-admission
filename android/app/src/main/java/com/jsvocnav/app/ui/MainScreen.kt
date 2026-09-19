package com.jsvocnav.app.ui

import android.content.Context
import android.widget.Toast
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Sort
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.jsvocnav.app.data.LocalStore
import com.jsvocnav.app.data.School
import com.jsvocnav.app.data.SchoolRepository
import com.jsvocnav.app.data.SortMode
import com.jsvocnav.app.service.DistanceService
import com.jsvocnav.app.service.LinkService
import com.jsvocnav.app.service.Scope
import com.jsvocnav.app.service.SchoolQuery
import com.jsvocnav.app.service.UpdateService
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MainScreen(
    context: Context,
    repository: SchoolRepository,
    store: LocalStore,
) {
    var loadResult by remember { mutableStateOf(repository.load()) }
    var keyword by remember { mutableStateOf("") }
    var city by remember { mutableStateOf(SchoolQuery.ALL) }
    var ownership by remember { mutableStateOf(SchoolQuery.ALL) }
    var sortMode by remember { mutableStateOf(SortMode.DEFAULT) }
    var scope by remember { mutableStateOf(Scope.ALL) }
    var favorites by remember { mutableStateOf(store.favorites()) }
    var recent by remember { mutableStateOf(store.recent()) }
    var selected by remember { mutableStateOf<School?>(null) }
    var showSources by remember { mutableStateOf(false) }
    var showDisclaimer by remember { mutableStateOf(false) }
    var menuOpen by remember { mutableStateOf(false) }
    var busy by remember { mutableStateOf(false) }
    val coroutineScope = rememberCoroutineScope()

    val origin = remember { store.origin }
    val distanceService = remember(origin) { DistanceService(origin) }

    val schools = loadResult.schools
    val cities = remember(schools) {
        listOf(SchoolQuery.ALL) + schools
            .filter { it.city.isNotBlank() }
            .groupingBy { it.city }
            .eachCount()
            .entries
            .sortedWith(compareByDescending<Map.Entry<String, Int>> { it.value }.thenBy { it.key })
            .map { it.key }
    }
    val distances = remember(schools, origin) { distanceService.distanceMap(schools) }
    val visible = remember(schools, keyword, city, ownership, sortMode, scope, favorites, recent, distances) {
        SchoolQuery.sort(
            SchoolQuery.filter(schools, keyword, city, ownership, favorites, recent, scope),
            sortMode,
            distances,
        )
    }

    fun toast(message: String) {
        Toast.makeText(context, message, Toast.LENGTH_SHORT).show()
    }

    // 详情页：用同一个 Compose 状态切换，并接管返回键
    val current = selected
    if (current != null) {
        BackHandler { selected = null }
        SchoolDetailScreen(
            school = current,
            distanceService = distanceService,
            originName = origin.name,
            isFavorite = current.id in favorites,
            onToggleFavorite = {
                val favorite = store.toggleFavorite(current.id)
                favorites = store.favorites()
                toast(if (favorite) "已收藏" else "已取消收藏")
            },
            onOpenUrl = { url ->
                if (!LinkService.openUrl(context, url)) toast("无法打开链接，可长按复制")
            },
            onOpenMap = {
                if (!LinkService.openRoute(context, origin, current)) toast("未找到可用的地图应用")
            },
            onBack = { selected = null },
        )
        return
    }

    Scaffold(
        topBar = {
            TopAppBar(
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.surface,
                ),
                title = {
                    Column {
                        Text("江苏高职提前招生", fontWeight = FontWeight.SemiBold)
                        val meta = loadResult.dataset.meta
                        val subtitle = buildString {
                            if (meta.dataYear > 0) append("数据年度 ${meta.dataYear}")
                            if (meta.lastVerified.isNotBlank()) {
                                if (isNotEmpty()) append("　")
                                append("核验 ${meta.lastVerified}")
                            }
                        }
                        if (subtitle.isNotBlank()) {
                            Text(
                                text = subtitle,
                                style = MaterialTheme.typography.labelMedium,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    }
                },
                actions = {
                    IconButton(onClick = { menuOpen = true }) {
                        Icon(Icons.Default.MoreVert, contentDescription = "更多")
                    }
                    DropdownMenu(expanded = menuOpen, onDismissRequest = { menuOpen = false }) {
                        DropdownMenuItem(
                            text = { Text("数据来源") },
                            onClick = { menuOpen = false; showSources = true },
                        )
                        DropdownMenuItem(
                            text = { Text("免责声明") },
                            onClick = { menuOpen = false; showDisclaimer = true },
                        )
                        DropdownMenuItem(
                            text = { Text(if (busy) "检查更新中…" else "检查数据更新") },
                            enabled = !busy,
                            onClick = {
                                menuOpen = false
                                busy = true
                                coroutineScope.launch {
                                    val message = UpdateService.check(repository, store)
                                    loadResult = repository.load(force = true)
                                    busy = false
                                    toast(message)
                                }
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
                .padding(padding),
        ) {
            // ---------------- 搜索 ----------------
            OutlinedTextField(
                value = keyword,
                onValueChange = { keyword = it },
                singleLine = true,
                leadingIcon = { Icon(Icons.Default.Search, contentDescription = null) },
                placeholder = { Text("搜索学校名、简称、城市、关键词…") },
                shape = RoundedCornerShape(12.dp),
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 8.dp),
            )

            // ---------------- 范围 ----------------
            LazyRow(
                contentPadding = PaddingValues(horizontal = 16.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                items(Scope.entries.toList()) { item ->
                    FilterChip(
                        selected = scope == item,
                        onClick = { scope = item },
                        label = { Text(item.label) },
                    )
                }
            }

            // ---------------- 城市 ----------------
            LazyRow(
                contentPadding = PaddingValues(horizontal = 16.dp, vertical = 6.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                items(cities) { item ->
                    FilterChip(
                        selected = city == item,
                        onClick = { city = item },
                        label = { Text(item) },
                    )
                }
            }

            // ---------------- 办学性质 + 排序 ----------------
            Row(
                verticalAlignment = Alignment.CenterVertically,
                modifier = Modifier.padding(horizontal = 16.dp),
            ) {
                listOf(SchoolQuery.ALL, "公办", "民办").forEach { item ->
                    FilterChip(
                        selected = ownership == item,
                        onClick = { ownership = item },
                        label = { Text(item) },
                        modifier = Modifier.padding(end = 8.dp),
                    )
                }
                Spacer(Modifier.weight(1f))
                SortMenu(current = sortMode, onPick = { sortMode = it })
            }

            Text(
                text = "共 ${schools.size} 所院校　显示 ${visible.size} 所",
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
            )

            // ---------------- 列表 ----------------
            if (visible.isEmpty()) {
                Column(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(32.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.Center,
                ) {
                    Text(
                        text = when (scope) {
                            Scope.FAVORITES -> "还没有收藏任何院校，点卡片右上角 ☆ 收藏"
                            Scope.RECENT -> "还没有浏览记录，打开任意院校的「详情」后会记录"
                            Scope.ALL -> "没有符合条件的院校，试试更换筛选条件"
                        },
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            } else {
                LazyColumn(
                    contentPadding = PaddingValues(horizontal = 16.dp, vertical = 8.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    items(visible, key = { it.id }) { school ->
                        SchoolCardView(
                            school = school,
                            distanceText = distanceService.shortText(school),
                            isFavorite = school.id in favorites,
                            onToggleFavorite = {
                                val favorite = store.toggleFavorite(school.id)
                                favorites = store.favorites()
                                toast(if (favorite) "已收藏" else "已取消收藏")
                            },
                            onOpenAdmission = {
                                if (!LinkService.openUrl(context, school.admissionEntryUrl)) {
                                    toast("未收录到可打开的链接")
                                }
                            },
                            onOpenMap = {
                                if (!LinkService.openRoute(context, origin, school)) {
                                    toast("未找到可用的地图应用")
                                }
                            },
                            onDetail = {
                                store.recordRecent(school.id)
                                recent = store.recent()
                                selected = school
                            },
                        )
                    }
                    item { Spacer(Modifier.height(16.dp)) }
                }
            }
        }
    }

    if (showSources) {
        InfoDialog(
            title = "数据来源",
            paragraphs = buildList {
                val meta = loadResult.dataset.meta
                if (meta.scope.isNotBlank()) add(meta.scope)
                addAll(meta.sources)
                if (meta.disclaimer.isNotBlank()) add(meta.disclaimer)
            },
            onDismiss = { showSources = false },
        )
    }

    if (showDisclaimer) {
        InfoDialog(
            title = "免责声明",
            paragraphs = listOf(
                loadResult.dataset.meta.disclaimer.ifBlank { DISCLAIMER_FALLBACK },
                "关于距离：界面显示的是「直线距离」（大圆距离），不是驾车距离，实际出行请以地图导航结果为准。",
                "关于数据：院校名单与各类官方入口来自公开信息整理，已尽力逐校核验，但可能滞后于院校官网最新发布。",
            ),
            onDismiss = { showDisclaimer = false },
        )
    }
}

@Composable
private fun SortMenu(current: SortMode, onPick: (SortMode) -> Unit) {
    var open by remember { mutableStateOf(false) }
    Row(verticalAlignment = Alignment.CenterVertically) {
        Icon(
            Icons.AutoMirrored.Filled.Sort,
            contentDescription = null,
            tint = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Spacer(Modifier.width(4.dp))
        TextButtonLike(text = current.label, onClick = { open = true })
        DropdownMenu(expanded = open, onDismissRequest = { open = false }) {
            SortMode.entries.forEach { mode ->
                DropdownMenuItem(
                    text = { Text(mode.label) },
                    onClick = { open = false; onPick(mode) },
                )
            }
        }
    }
}

@Composable
private fun TextButtonLike(text: String, onClick: () -> Unit) {
    androidx.compose.material3.TextButton(onClick = onClick) {
        Text(text, maxLines = 1, overflow = TextOverflow.Ellipsis)
    }
}

const val DISCLAIMER_FALLBACK =
    "本软件仅用于整理和导航江苏省高职院校提前招生相关公开信息，不属于江苏省教育考试院或任何高校官方招生平台。"
