package com.jsvocnav.app.ui

import android.content.Context
import android.widget.Toast
import androidx.activity.compose.BackHandler
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectVerticalDragGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Sort
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.ExpandLess
import androidx.compose.material.icons.filled.ExpandMore
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material.icons.filled.KeyboardArrowUp
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
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalFocusManager
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
    // 筛选面板默认收起：大字体手机上不能让它把正文挤成半屏
    var filtersExpanded by remember { mutableStateOf(false) }
    val coroutineScope = rememberCoroutineScope()
    val focusManager = LocalFocusManager.current

    // 启动时不自动聚焦搜索框（否则真机会弹出输入法，直接占掉半屏）
    LaunchedEffect(Unit) {
        focusManager.clearFocus(force = true)
    }

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
    val activeFilterCount = listOf(
        city != SchoolQuery.ALL,
        ownership != SchoolQuery.ALL,
        sortMode != SortMode.DEFAULT,
    ).count { it }

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
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(
                            text = "江苏高职提前招生",
                            fontWeight = FontWeight.SemiBold,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                        )
                        val dataYear = loadResult.dataset.meta.dataYear
                        if (dataYear > 0) {
                            Spacer(Modifier.width(6.dp))
                            Surface(
                                color = MaterialTheme.colorScheme.primaryContainer,
                                shape = RoundedCornerShape(8.dp),
                            ) {
                                Text(
                                    text = "$dataYear",
                                    style = MaterialTheme.typography.labelMedium,
                                    color = MaterialTheme.colorScheme.onPrimaryContainer,
                                    modifier = Modifier.padding(horizontal = 7.dp, vertical = 1.dp),
                                )
                            }
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
            // ---------------- 可收起的顶部抽屉 ----------------
            // 收起时只剩一条「把手」：小三角 + 当前条件摘要。点按或上下滑动都能开合，
            // 展开后才出现搜索框与全部筛选项——正文因此始终占满剩余空间。
            val summaryText = remember(scope, city, ownership, sortMode, keyword) {
                buildList {
                    add(scope.label)
                    if (city != SchoolQuery.ALL) add(city)
                    if (ownership != SchoolQuery.ALL) add(ownership)
                    if (sortMode != SortMode.DEFAULT) add(sortMode.shortLabel)
                    if (keyword.isNotBlank()) add("“$keyword”")
                }.joinToString(" · ")
            }
            val hasActiveFilter = keyword.isNotBlank() ||
                city != SchoolQuery.ALL ||
                ownership != SchoolQuery.ALL ||
                sortMode != SortMode.DEFAULT

            Surface(
                color = MaterialTheme.colorScheme.surface,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    modifier = Modifier
                        .fillMaxWidth()
                        .clickable { filtersExpanded = !filtersExpanded }
                        .pointerInput(Unit) {
                            // 上滑收起、下滑展开（与「很多应用」的抽屉手感一致）
                            var accumulated = 0f
                            detectVerticalDragGestures(
                                onDragStart = { accumulated = 0f },
                                onDragEnd = {
                                    if (accumulated <= -HANDLE_DRAG_THRESHOLD) {
                                        filtersExpanded = false
                                    } else if (accumulated >= HANDLE_DRAG_THRESHOLD) {
                                        filtersExpanded = true
                                    }
                                },
                            ) { _, dragAmount -> accumulated += dragAmount }
                        }
                        .padding(start = 12.dp, end = 8.dp, top = 2.dp, bottom = 2.dp),
                ) {
                    Icon(
                        imageVector = if (filtersExpanded) {
                            Icons.Default.KeyboardArrowUp
                        } else {
                            Icons.Default.KeyboardArrowDown
                        },
                        contentDescription = if (filtersExpanded) "收起筛选" else "展开筛选",
                        tint = MaterialTheme.colorScheme.primary,
                    )
                    Spacer(Modifier.width(4.dp))
                    Text(
                        text = summaryText,
                        style = MaterialTheme.typography.bodyMedium,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                        modifier = Modifier.weight(1f),
                    )
                    if (hasActiveFilter) {
                        TextButton(
                            onClick = {
                                keyword = ""
                                city = SchoolQuery.ALL
                                ownership = SchoolQuery.ALL
                                sortMode = SortMode.DEFAULT
                            },
                        ) {
                            Text("清空", maxLines = 1)
                        }
                    }
                }
            }

            AnimatedVisibility(visible = filtersExpanded) {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 16.dp),
                    verticalArrangement = Arrangement.spacedBy(4.dp),
                ) {
                    OutlinedTextField(
                        value = keyword,
                        onValueChange = { keyword = it },
                        singleLine = true,
                        leadingIcon = { Icon(Icons.Default.Search, contentDescription = null) },
                        trailingIcon = {
                            if (keyword.isNotEmpty()) {
                                IconButton(onClick = { keyword = "" }) {
                                    Icon(Icons.Default.Close, contentDescription = "清空搜索")
                                }
                            }
                        },
                        placeholder = { Text("搜索学校、城市、关键词", maxLines = 1) },
                        shape = RoundedCornerShape(12.dp),
                        modifier = Modifier.fillMaxWidth(),
                    )

                    LazyRow(
                        modifier = Modifier.clipToBounds(),
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        items(Scope.entries.toList()) { item ->
                            FilterChip(
                                selected = scope == item,
                                onClick = { scope = item },
                                label = { Text(item.label, maxLines = 1) },
                            )
                        }
                    }

                    Text(
                        text = "城市",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        items(cities) { item ->
                            FilterChip(
                                selected = city == item,
                                onClick = { city = item },
                                label = { Text(item, maxLines = 1) },
                            )
                        }
                    }
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Text(
                            text = "性质",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        Spacer(Modifier.width(8.dp))
                        listOf(SchoolQuery.ALL, "公办", "民办").forEach { item ->
                            FilterChip(
                                selected = ownership == item,
                                onClick = { ownership = item },
                                label = { Text(item, maxLines = 1) },
                                modifier = Modifier.padding(end = 6.dp),
                            )
                        }
                    }
                    // 排序单独一行：与性质挤在一行时，排序文字会被压成一个省略号
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Text(
                            text = "排序",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        Spacer(Modifier.width(8.dp))
                        SortMenu(current = sortMode, onPick = { sortMode = it })
                    }
                    Spacer(Modifier.height(4.dp))
                }
            }

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
                            Scope.RECENT -> "还没有浏览记录，点开任意院校后会自动记录"
                            Scope.ALL -> "没有符合条件的院校，试试更换筛选条件"
                        },
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            } else {
                LazyColumn(
                    contentPadding = PaddingValues(horizontal = 16.dp, vertical = 6.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    item(key = "__count__") {
                        Text(
                            text = "共 ${schools.size} 所院校　显示 ${visible.size} 所",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
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
                add(
                    buildString {
                        if (meta.dataYear > 0) append("数据年度：${meta.dataYear} 年　")
                        if (meta.lastVerified.isNotBlank()) append("核验日期：${meta.lastVerified}　")
                        append("收录 ${loadResult.schools.size} 所")
                    }
                )
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

/** 抽屉把手上下滑多少像素才触发开合 */
private const val HANDLE_DRAG_THRESHOLD = 40f
